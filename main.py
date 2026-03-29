#!/usr/bin/env python3

from pathlib import Path
import json
import subprocess
import sys
import urllib.request

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def generate_hydra_urls(maintainer_name: str) -> dict[str, str]:
    arg0_dirname = Path(sys.argv[0]).resolve().parent
    maintained_derivations_with_hydra_urls = "{}/maintained-derivations-with-hydra-urls.nix".format(arg0_dirname)
    generate_hydra_urls_cmd_args = [
        "nix-build",
        maintained_derivations_with_hydra_urls,
        "--no-out-link",
        "--argstr",
        "maintainer",
        maintainer_name
    ]
    generate_hydra_urls_cmd = subprocess.run(generate_hydra_urls_cmd_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if generate_hydra_urls_cmd.returncode == 0:
        generate_hydra_urls_out_path = generate_hydra_urls_cmd.stdout.strip().splitlines()[-1]
        with open(generate_hydra_urls_out_path, "r", encoding="utf-8") as generate_hydra_urls_out_path_file:
            generate_hydra_urls_out_path_file_content = generate_hydra_urls_out_path_file.read()
            generated_hydra_urls = json.loads(generate_hydra_urls_out_path_file_content)
            return generated_hydra_urls
    else:
        print("ERROR: running `{}`\nSTDERR: {}".format(" ".join(generate_hydra_urls_cmd_args), generate_hydra_urls_cmd.stderr))
        sys.exit(1)


def get_hydra_job_id_statuses(hydra_urls: dict[str, str]) -> dict[str, dict[dict[str, str]]]:
    new_hydra_urls = {}
    for job_name in hydra_urls.keys():
        hydra_job_request = urllib.request.Request(hydra_urls[job_name], headers={"Accept": "application/json"})
        with urllib.request.urlopen(hydra_job_request) as hydra_job_response:
            hydra_job_data = json.loads(hydra_job_response.read().decode('utf-8'))
            new_hydra_urls[job_name] = {}
            new_hydra_urls[job_name]["buildstatus"] = hydra_job_data["buildstatus"]
            new_hydra_urls[job_name]["finished"] = hydra_job_data["finished"]
            new_hydra_urls[job_name]["id"] = hydra_job_data["id"]
            new_hydra_urls[job_name]["job"] = hydra_job_data["job"]
            new_hydra_urls[job_name]["starttime"] = hydra_job_data["starttime"]
    return new_hydra_urls


def determine_job_status(hydra_job_matrix: dict[str, dict[dict[str, str]]]) -> int:
    exit_status = 0
    notice_messages = []
    warning_messages = []
    for hydra_job in hydra_job_matrix.values():
        branched = False
        # <https://github.com/NixOS/hydra/blob/b88b06dd3c857ad4fcd23f406fa95960803aa067/hydra-api.yaml#L1073-L1075>
        if hydra_job["finished"] == 0:
            # <https://github.com/NixOS/hydra/blob/b88b06dd3c857ad4fcd23f406fa95960803aa067/hydra-api.yaml#L1059-L1061>
            if hydra_job["starttime"] == 0:
                branched = True
                notice_messages.append("Note: `{}` ('https://hydra.nixos.org/build/{}') => QUEUED".format(hydra_job["job"], hydra_job["id"]))

            elif hydra_job["starttime"] > 0:
                branched = True
                notice_messages.append("Note: `{}` ('https://hydra.nixos.org/build/{}') => progress".format(hydra_job["job"], hydra_job["id"]))

        elif hydra_job["finished"] == 1:
            # <https://github.com/NixOS/hydra/blob/b88b06dd3c857ad4fcd23f406fa95960803aa067/hydra-api.yaml#L1079-L1097>
            match hydra_job["buildstatus"]:
                case 0:
                    branched = True
                    notice_messages.append("Note: `{}` ('https://hydra.nixos.org/build/{}') => SUCCESSFUL".format(hydra_job["job"], hydra_job["id"]))

                case 1:
                    branched = True
                    warning_messages.append("Warning: `{}` ('https://hydra.nixos.org/build/{}') => FAILED".format(hydra_job["job"], hydra_job["id"]))
                    exit_status = 1

                case 2:
                    branched = True
                    warning_messages.append("Warning: `{}` ('https://hydra.nixos.org/build/{}') => DEPENDENCY FAILED".format(hydra_job["job"], hydra_job["id"]))
                    exit_status = 1

                case 3:
                    branched = True
                    warning_messages.append("Warning: `{}` ('https://hydra.nixos.org/build/{}') => ABORTED (3)".format(hydra_job["job"], hydra_job["id"]))
                    exit_status = 1

                case 4:
                    branched = True
                    warning_messages.append("Warning: `{}` ('https://hydra.nixos.org/build/{}') => CANCELLED BY THE USER".format(hydra_job["job"], hydra_job["id"]))
                    exit_status = 1

                case 6:
                    branched = True
                    warning_messages.append("Warning: `{}` ('https://hydra.nixos.org/build/{}') => FAILED WITH OUTPUT".format(hydra_job["job"], hydra_job["id"]))
                    exit_status = 1

                case 7:
                    branched = True
                    warning_messages.append("Warning: `{}` ('https://hydra.nixos.org/build/{}') => TIMED OUT".format(hydra_job["job"], hydra_job["id"]))
                    exit_status = 1

                case 9:
                    branched = True
                    warning_messages.append("Warning: `{}` ('https://hydra.nixos.org/build/{}') => ABORTED (9)".format(hydra_job["job"], hydra_job["id"]))
                    exit_status = 1

                case 10:
                    branched = True
                    warning_messages.append("Warning: `{}` ('https://hydra.nixos.org/build/{}') => LOG SIZE LIMIT EXCEEDED".format(hydra_job["job"], hydra_job["id"]))
                    exit_status = 1

                case 11:
                    branched = True
                    warning_messages.append("Warning: `{}` ('https://hydra.nixos.org/build/{}') => OUTPUT SIZE LIMIT EXCEEDED".format(hydra_job["job"], hydra_job["id"]))
                    exit_status = 1

                case _:
                    branched = True
                    warning_messages.append("Warning: `{}` ('https://hydra.nixos.org/build/{}') has an unexpected `buildstatus`: {}".format(hydra_job["job"], hydra_job["id"], hydra_job["buildstatus"]))
                    exit_status = 1

        if not branched:
            exit_status = 1
            print("Error: For `{}` ('https://hydra.nixos.org/build/{}'), no branch was executed".format(hydra_job["job"], hydra_job["id"]))
            break

    for ze_msg in notice_messages + warning_messages:
        eprint(ze_msg)

    if exit_status == 0:
        eprint("Notice: All of the maintained derivations have been built successfully")

    return exit_status


def main(maintainer_name: str) -> int:
    eprint("Notice: Determining `pkgs` and `nixosTests` maintained by `lib.maintainers.{}`".format(maintainer_name))
    generated_hydra_urls = generate_hydra_urls(maintainer_name)
    if len(generated_hydra_urls) == 0:
        eprint("Warning: Could not find any packages nor nixosTests maintained by '{}'".format("lib.maintainers."+maintainer_name))
        sys.exit(0)

    eprint("Notice: Getting latest Hydra build status for the maintained derivations")
    hydra_job_matrix = get_hydra_job_id_statuses(generated_hydra_urls)
    exit_status = determine_job_status(hydra_job_matrix)

    return exit_status


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Error: The maintainer name is a required argument to this script")
        sys.exit(1)
    maintainer_name = sys.argv[1]
    exit_status = main(maintainer_name)
    sys.exit(exit_status)
