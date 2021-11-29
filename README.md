# Kalhor Mouse Management pipeline
Python notebook for organizing information in the kalhor lab mouse colony spreadsheet.
The workflow as it currently is resides entirely in:

- mouse_mgmt.ipynb, where the work happens
- colonymgmt.py, which has various semi-helpful functions + a lot of cruft.

It currently uses a local client token linked to the google API. Notes on how to do this can be found [here](https://github.com/kathleenleeper/code-config-snippets/blob/main/google-auth-python.md).

It is also relatively adaptable to pull the same data from an uploaded CSV file, although that's not the current use case.
