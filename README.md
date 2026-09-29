# Open Source India 2026: Exasol booth assets

The demos and the booth video from Exasol's booth at **Open Source India, 7–8 October 2026**.

## Video

**[Exasol-Complete-Story-v12.mp4](https://github.com/yuvi-ex/opensourceeventassets/releases/download/v1.0-event/Exasol-Complete-Story-v12.mp4)** is the booth video (161 MB).
It's attached to the [`v1.0-event` release](https://github.com/yuvi-ex/opensourceeventassets/releases/tag/v1.0-event) because it's too large for git.

## Slides

Coming soon.

## The builds

| Build | What it's for | Platform |
|---|---|---|
| [`clinical-trials-demo/`](clinical-trials-demo/) | Clinical trial intelligence. Ask a question in English, an agent writes and runs SQL on Exasol over MCP, and it answers citing trial IDs. The demo shows why a semantic layer is where "which trials count" decisions belong. | Exasol Personal (macOS / Linux) with the PYTHON3 SLC, Docker, and Python 3 + Streamlit (`app/run.sh`). An `ANTHROPIC_API_KEY` is optional, for the agent. |
| [`real-time-banking-fraud-pipeline/`](real-time-banking-fraud-pipeline/) | Real-time card fraud detection: PostgreSQL → Debezium CDC → Kafka → Exasol → a Python ML UDF scores each transaction. `story_demo/` is the booth's "Anatomy of a Card Theft" stage app: seven acts, with every number read live. | Docker Compose (Postgres, Kafka, Schema Registry, Kafka Connect) plus Exasol, and Python 3 + Streamlit. Setup scripts are included for macOS/Linux (`deploy.sh`) and Windows (`deploy.ps1`). |

Each folder has its own README with full setup steps.

### Notes

- **clinical-trials-demo:** the large generated files (vectors, the model, the lakehouse engine) are not included. The numbered scripts rebuild them. Copy `.env.example` to `.env` for the API key.
- **real-time-banking-fraud-pipeline:** `docker-compose.override.example.yml` is the booth's local override. It remaps ports and adds a Kafka listener that an Exasol Personal VM reaches through the macOS host bridge (`192.168.64.1`). To use it, rename it to `docker-compose.override.yml`.

## Credits and licensing

- `clinical-trials-demo/` and the rest of this repository are under the [MIT License](LICENSE).
- `real-time-banking-fraud-pipeline/` was written by Sanjay Gaudamchand (Exasol). The `story_demo/` stage app was added for the booth. This folder is **not** covered by the MIT license in this repository.
