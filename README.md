# PtoCalc

This is a PTO calculator to track how many hours or days you will have after using planned PTO.

## AWS App Runner

This repo includes the basics needed to deploy the app to AWS App Runner from a private GitHub repository:

- `requirements.txt` with pinned Python dependencies
- `apprunner.yaml` with the App Runner build and run settings
- `.streamlit/config.toml` with a minimal toolbar configuration

The app starts with:

```bash
streamlit run PtoCalc.py --server.port 8080 --server.address 0.0.0.0
```

When creating the App Runner service, point it at this repository and branch, then let App Runner read `apprunner.yaml`.
