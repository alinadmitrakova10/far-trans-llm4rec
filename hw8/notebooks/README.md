# Google Colab

Open `hw8_user_history_encoder.ipynb` manually at https://colab.research.google.com/ (File → Upload notebook).

First run `python hw8/src/bundle.py` locally. Upload `hw8/outputs/workflow_bundle.zip` in the first notebook cell, install pinned dependencies, restart the kernel, and continue with hardware and data upload. Upload the official dataset ZIP or four source CSVs separately. Compare the locally generated `baseline/protocol.json` when prompted.

The Qwen cell defaults to `AUTHOR_APPROVED_QWEN_RUN = False`. Change it only after separate permission to start the Colab/GPU run. The notebook has no saved execution outputs; inference has not been verified in Colab by preparing this file.

Download outputs before ending the runtime, unpack under `hw8/outputs/colab/`, and clear all notebook cell outputs before adding notebook changes to Git.
