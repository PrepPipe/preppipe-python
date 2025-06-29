import os
import subprocess
import json
import argparse
from pathlib import Path

def collect_licenses():
  parser = argparse.ArgumentParser(description="Collect third-party licenses.")
  parser.add_argument(
    "--output-dir",
    type=str,
    default="licenses",
    help="Directory to save the license files.",
  )
  args = parser.parse_args()
  output_dir = Path(args.output_dir)
  output_dir.mkdir(exist_ok=True)
  summary_file = output_dir / "0_third_party_summary.txt"

  print("Running pip-licenses...")

  # Run pip-licenses with license text included
  result = subprocess.run(
    [
      "pip-licenses",
      "--format=json",
      "--with-license-file",
      "--with-authors",
      "--from=mixed",  # Handles venv and non-venv cases
    ],
    capture_output=True,
    text=True,
    check=True,
  )

  packages = json.loads(result.stdout)

  summary_lines = ["Third-Party License Summary", "=" * 40, ""]

  for pkg in packages:
    name = pkg["Name"]
    # ignore our own "preppipe"
    if name == "preppipe":
      continue
    version = pkg["Version"]
    license_type = pkg["License"]
    author = pkg["Author"]
    license_text = pkg["LicenseFile"]
    if license_text == "UNKNOWN":
      license_text = None
    elif os.path.isfile(license_text):
      with open(license_text, "r", encoding="utf-8") as f:
        license_text = f.read()

    summary_lines.append(f"{name}=={version} ({license_type}) - {author}")

    # Write license text to individual files
    license_path = output_dir / f"{name}_LICENSE.txt"
    with open(license_path, "w", encoding="utf-8") as f:
      f.write(f"{name} ({version})\n")
      f.write(f"License: {license_type}\n")
      f.write(f"Author: {author}\n\n")
      f.write(license_text or "[No license text found]")

  # Write summary file
  with open(summary_file, "w", encoding="utf-8") as f:
    f.write("\n".join(summary_lines))

  print(f"License files saved to: {output_dir.absolute()}")

  for line in summary_lines:
    print(ascii(line))

if __name__ == "__main__":
  collect_licenses()
