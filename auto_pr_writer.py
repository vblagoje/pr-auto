import hashlib
import json
import os
import re
import sys
from typing import Optional, List

import requests
from haystack import Pipeline
from haystack.components.connectors import OpenAPIServiceConnector
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.dataclasses import ChatMessage


def load_file_from(locations: List[str]) -> str:
    """
    Loads the content of a file from given locations.
    :param locations: a list of file paths or URLs
    :return: file content as a string
    :raises FileNotFoundError: If the file cannot be loaded from any of the given locations.
    """
    for location in locations:
        try:
            # If it's a URL, make a request and return the text content
            if location.startswith("http://") or location.startswith("https://"):
                response = requests.get(location)
                if response.status_code == 200:
                    return response.text

            # If it's a local file path, try to open and return the content
            elif os.path.exists(location):
                with open(location, "r") as file:
                    return file.read()

        except Exception as e:
            print(f"Failed to load from {location}. Error: {e}")

    raise FileNotFoundError(f"Failed to load from any of the locations: {locations}")


def generate_pr_text(
    github_repo: str, base_branch: str, pr_branch: str, model_name: str, custom_instruction: Optional[str] = None
) -> ChatMessage:
    """
    Generates a GitHub Pull Request (PR) text based on user instructions.

    :param github_repo: The GitHub repository in the format 'owner/repo'.
    :type github_repo: str
    :param base_branch: The base branch of the PR.
    :type base_branch: str
    :param pr_branch: The PR branch.
    :type pr_branch: str
    :param model_name: The model to use for PR text generation.
    :type model_name: str
    :param custom_instruction: Optional custom instructions for PR text generation, like "Be brief, one
    sentence per section".
    :type custom_instruction: Optional[str]
    :return: A ChatMessage containing the generated PR text along with the generation statistics in the metadata.
    :rtype: ChatMessage
    :raises ValueError: If the OPENAI_API_KEY environment variable is not set.
    """
    # we try loading from different locations as script can run in different environments
    # e.g. locally, in docker, in GitHub Actions
    openapi_spec = json.loads(load_file_from(["github_compare_spec.json", "https://bit.ly/github_compare"]))

    system_prompt_text = os.environ.get("AUTO_PR_WRITER_SYSTEM_MESSAGE") or load_file_from(
        ["system_prompt.txt", "https://bit.ly/auto_pr_writer_system_prompt"]
    )

    # a GitHub access token is required to invoke the GitHub compare service and avoid rate limiting
    service_auth = {"Github API": os.environ.get("GITHUB_TOKEN")}

    invoke_service_pipe = Pipeline()
    invoke_service_pipe.add_component("openapi_container", OpenAPIServiceConnector(service_auth))
    invocation_payload = create_invocation_payload(
        base_ref=base_branch,
        head_ref=pr_branch,
        repository=github_repo.split("/")[0],
        project=github_repo.split("/")[1],
    )

    invocation_payload = json.dumps([invocation_payload])
    service_response = invoke_service_pipe.run(
        data={"messages": [ChatMessage.from_assistant(invocation_payload)], "service_openapi_spec": openapi_spec}
    )

    github_service_response: List[ChatMessage] = service_response["openapi_container"]["service_response"]
    github_service_response_json = json.loads(github_service_response[0].content)
    # take the diff files portion of the response to save tokens and to fit into the smaller LLM context windows
    # other parts of the response are not relevant for PR text generation
    # and only waste token$ and LLM context window
    diff_message = ChatMessage.from_user(json.dumps(github_service_response_json["files"]))

    system_message = ChatMessage.from_system(system_prompt_text)
    if custom_instruction:
        github_pr_prompt_messages = [system_message] + [diff_message] + [ChatMessage.from_user(custom_instruction)]
    else:
        github_pr_prompt_messages = [system_message] + [diff_message]

    gen_pr_text_pipeline = Pipeline()
    # empirically, max_tokens 2560 is enough to generate a PR text
    # Note that you can use OPENAI_ORG_ID to set the organization ID for your OpenAI API key to track usage and costs
    llm = OpenAIChatGenerator(model=model_name, generation_kwargs={"max_tokens": 2560})
    gen_pr_text_pipeline.add_component("llm", llm)

    final_result = gen_pr_text_pipeline.run(data={"messages": github_pr_prompt_messages})
    return final_result["llm"]["replies"][0]


def extract_custom_instruction(bot_name: str, user_instruction: str) -> str:
    """
    Extracts custom instruction from a user instruction string by searching for specific pattern in the user
    instruction string to find and return custom instructions.

    The function uses regular expressions to find the custom instruction following the bot name in the user instruction

    :param bot_name: The name of the bot to search for in the user instruction string.
    :type bot_name: str
    :param user_instruction: The complete user instruction string, potentially containing custom instructions.
    :type user_instruction: str
    :return: The extracted custom instruction, if found; otherwise, an empty string.
    :rtype: str
    """
    # Search for the message following @bot_name
    match = re.search(rf"@{re.escape(bot_name)}\s+(.*)", user_instruction)
    return match.group(1) if match else ""


def create_invocation_payload(base_ref: str, head_ref: str, repository: str, project: str):
    """
    Creates an invocation payload for the GitHub compare service.
    :param base_ref: A string containing the base branch of the PR e.g. 'main'.
    :param head_ref: A string containing the PR branch.
    :param repository: A string containing the GitHub repository owner e.g. 'deepset-ai'.
    :param project: A string containing the GitHub repository name e.g. 'haystack'.
    :return: A dictionary containing the invocation payload.
    """
    invocation_payload = {
        "id": "some_irrelevant_id",
        "function": {
            "arguments": f'{{"parameters": {{"basehead": "{base_ref}...{head_ref}", '
            f'"owner": "{repository}", "repo": "{project}"}}}}',
            "name": "compare_branches",
        },
        "type": "function",
    }
    return invocation_payload


def contains_skip_instruction(text):
    return bool(re.search(r"\bskip\b", text, re.IGNORECASE))


def write_to_github_output(output_name: str, output_value: str):
    """
    Writes the output_name and output_value pair to the GITHUB_OUTPUT file in the format expected by GitHub Actions.
    :param output_name: The name of the output.
    :param output_value: The value of the output.
    """

    # needed because by default multiple lines outputs are not supported in GitHub Actions
    # see https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#multiline-strings
    hash_object = hashlib.sha256("some_random_data".encode())
    delimiter = hash_object.hexdigest()

    github_env = os.environ.get("GITHUB_OUTPUT", None)

    if github_env:
        # Write to the GITHUB_OUTPUT file only if we are running in GitHub Actions
        with open(github_env, "a") as env_file:
            env_file.write(f"{output_name}<<{delimiter}\n")
            env_file.write(f"{output_value}\n")
            env_file.write(f"{delimiter}\n")


if __name__ == "__main__":
    required_env_vars = {
        "GITHUB_TOKEN": "Please provide GITHUB_TOKEN as environment variable.",
        "OPENAI_API_KEY": "Please set OPENAI_API_KEY environment variable to your OpenAI API key.",
    }

    # account for the bot name being set to "" or None, use default value if not set
    env_var_tmp = os.environ.get("AUTO_PR_WRITER_BOT_NAME")
    bot_name = "auto-pr-writer-bot" if not env_var_tmp else env_var_tmp

    for var, msg in required_env_vars.items():
        if not os.environ.get(var):
            print(msg)
            sys.exit(1)

    user_message = os.environ.get("AUTO_PR_WRITER_USER_MESSAGE")
    custom_user_instruction = extract_custom_instruction(bot_name, user_message) if user_message else None

    if custom_user_instruction and contains_skip_instruction(custom_user_instruction):
        print("Exiting auto-pr-writer, user instruction contains the word 'skip'.")
        sys.exit(0)

    # Fetch required information from environment variables or command-line arguments
    if len(sys.argv) < 2:
        github_repository, base_ref, head_ref = (
            os.environ.get(var) for var in ["GITHUB_REPOSITORY", "BASE_REF", "HEAD_REF"]
        )
    else:
        github_repository, base_ref, head_ref = sys.argv[1:4]

    # Validate required parameters
    if not all([github_repository, base_ref, head_ref]):
        print(
            "Please provide GITHUB_REPOSITORY, BASE_REF, HEAD_REF as environment variables or command-line arguments."
        )
        sys.exit(1)

    # Ok, we are gtg, generate PR text
    generated_pr_text_message = generate_pr_text(
        github_repo=github_repository,
        base_branch=base_ref,
        pr_branch=head_ref,
        model_name=os.environ.get("GENERATION_MODEL") or "gpt-4-1106-preview",  # long context, change with caution
        custom_instruction=custom_user_instruction,
    )
    generated_pr_text = generated_pr_text_message.content

    attribution_message = os.environ.get("AUTO_PR_WRITER_ATTRIBUTION_MESSAGE")
    if attribution_message:
        generated_pr_text = f"{generated_pr_text}\n\n{attribution_message}"

    # output the generated PR text and the generation statistics to the console (i.e. for docker experiments)
    print(f"{generated_pr_text}\n\n{generated_pr_text_message.meta}")

    # write the generated PR text and the generation statistics to the GITHUB_OUTPUT file
    write_to_github_output("generated_pr_text", generated_pr_text)
    write_to_github_output("generated_pr_text_stats", str(generated_pr_text_message.meta))
