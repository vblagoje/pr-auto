FROM deepset/haystack:base-main

# Copy files to the root directory (Don't change)
# Enables smooth GitHub Actions integration
# Github runner that spins up a docker container sets the working dir to /github/workspace and mounts
# the project directory to /github/workspace, thus we copy the files to the root directory
# and run the script from there, the downside is that we then need to download:
# - github_compare_spec.json
# - system_prompt.txt
# If you know a better way to do this, please let me know
COPY . /

# Install required packages
RUN pip install --no-cache-dir -r /requirements.txt

# Set the entrypoint
ENTRYPOINT ["python", "/auto_pr_writer.py"]