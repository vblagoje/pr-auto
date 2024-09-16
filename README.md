# PR Auto

![License](https://img.shields.io/github/license/vblagoje/pr-auto)
![Docker Pulls](https://img.shields.io/docker/pulls/vblagoje/openapi-rag-service)

## Description
PR Auto is a GitHub Action designed to automatically generate pull request descriptions using Large Language Models (LLMs). By default, it utilizes OpenAI's models, but it also supports integration with a variety of other LLM providers such as fireworks.ai, together.xyz, anyscale, octoai, etc., allowing users to select their preferred provider and LLMs to best suit their needs. This action can be customized with system and user-provided prompts to tailor the PR description generation.

![Auto PR  Demo](https://raw.githubusercontent.com/vblagoje/various/main/auto-pr-writer-optimize.gif)

## Usage
The minimum requirements to use this action with its default settings are:
- You have an `OPENAI_API_KEY` set in your repository secrets.
- You have given "Read and write permissions" to workflows in your repository:
  - Settings -> Actions -> General -> Workflow Permissions: Select 'Read and write permissions' and Save
- Add a workflow to your repository to trigger this action when a new PR is created, edited or reopened. See the example below.
- (Optional) Use the [example pull request template in your repository to create an initial PR description](https://github.com/vblagoje/pr-auto/blob/main/.github/pull_request_template.md)

## Minimal Example Workflow

Here's a minimal example of how to use the PR Auto in a pull request workflow:

```yaml
name: Pull Request Text Generator Workflow

on:
  pull_request_target:
    types: [opened]

jobs:
  generate-pr-text:
    runs-on: ubuntu-latest
    steps:
      - name: Generate PR Description
        uses: vblagoje/pr-auto@v1
        id: pr_auto
        with:
          openai_api_key: ${{ secrets.OPENAI_API_KEY }}

      - name: Update PR description
        uses: vblagoje/update-pr@v1
        with:
          pr-body: ${{ steps.pr_auto.outputs.pr-text }}
```
### Important Security Consideration
Using PR Auto with the `pull_request_target` event is secure and allows PRs from forks. This approach:

- Doesn't check out any code from forks, eliminating the risk of running untrusted code.
- Only generates PR descriptions based on pull request metadata.
- Uses a trusted action (vblagoje/update-pr) to update the PR description.

Needless to say, don't use `pr-auto` in conjunction with fetching code from untrusted PR forks (e.g. via `actions/checkout`), especially when triggered by the `pull_request_target` event.  Instead, follow the example above to safely use pr-auto.

For more detailed information on these security considerations, refer to:
- [GitHub Actions documentation on pull_request_target](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#pull_request_target)
- [GitHub Security Lab article: "Keeping your GitHub Actions and workflows secure: Preventing pwn requests"](https://securitylab.github.com/research/github-actions-preventing-pwn-requests/)

## Inputs

- `github_token` **Required** GITHUB_TOKEN or a repository-scoped Personal Access Token (PAT), defaulting to the GitHub token provided by the GitHub Actions runner. It is essential for invoking the GitHub API REST service to retrieve Pull Request details. Using GITHUB_TOKEN permits actions to access both public and private repositories, helping to bypass rate limits imposed by the GitHub API.

- `openai_api_key`
**Required** The OpenAI API key for authentication. Note that this key could be from other LLM providers as well.

- `openai_base_url` **Optional** The base URL for the OpenAI API. Using this input one can use different LLM providers (e.g. fireworks.ai, together.xyz, anyscale, octoai etc.) Defaults to https://api.openai.com/v1

- `github_repository`**Optional** The GitHub repository where the pull request is made. Defaults to the current repository.

- `base_branch` **Optional** The base (target) branch in the pull request. Defaults to the base branch of the current PR.

- `head_branch` **Optional** The head (source) branch in the pull request. Defaults to the head branch of the current PR.

- `generation_model` **Optional** The generation_model specifies the model to use for PR text generation. While it defaults to gpt-4o from OpenAI, users have the flexibility to select from a range of models available from various LLM providers, including but not limited to fireworks.ai, together.xyz, anyscale, octoai, etc. This allows for more tailored and varied text generation capabilities to meet diverse needs and preferences.

- `function_calling_model` **Optional** LLM to use for function calling (service parameter resolution, output formatting etc). Defaults to gpt-3.5-turbo from OpenAI.

- `system_prompt` **Optional** System message/prompt to help the model generate the PR description.

- `user_prompt` **Optional** Additional user prompt to help the model generate the PR description.

- `bot_name` **Optional** The name of the bot so users can guide LLM generation with @bot_name from PR comments. Defaults to pr-auto-bot


## Contributing

If you have ideas for enhancing PR Auto, or if you encounter a bug, we encourage you to contribute by opening an issue or a pull request.
The core of this GitHub Action is built on top of Docker image of the [vblagoje/openapi-rag-service](https://github.com/vblagoje/openapi-rag-service/) project. 
Therefore, for contributions beyond minor edits to the `action.yml` or `README.md`, please direct your pull requests to 
the [vblagoje/openapi-rag-service](https://github.com/vblagoje/openapi-rag-service/) GitHub repository.

## License
This project is licensed under [Apache 2.0 License](LICENSE).
