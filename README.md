# AI Escrow Arbitrator

## Short Description

A Telegram and web-based AI escrow bot that helps clients and freelancers manage trustless job payments using Groq AI arbitration and x402/GOAT Testnet payment flows.

## Repository Description

AI Escrow Arbitrator is a freelance escrow automation project that combines a Telegram bot, FastAPI backend, web dashboard, Groq AI evaluation, and demo x402 payment handling. It helps clients post paid jobs, lets freelancers submit completed work, and uses AI to decide whether payment should be fully released, partially released, or refunded.

## Description

AI Escrow Arbitrator is a Telegram bot and FastAPI web app for freelance escrow workflows. Clients can create jobs, freelancers can submit work, and Groq AI evaluates submissions to approve payment, release partial payment, or refund the client.

The app is designed for small freelance tasks where both sides need a neutral evaluator. A client posts a job with an amount and deadline, the freelancer submits completed work, and the AI arbitrator scores the work against the original description. Based on the score, the system decides whether to approve full payment, release a partial payment, or refund the client. Users can also raise disputes, check freelancer reputation, view job history, and monitor activity from the web dashboard.

The project includes:

- Telegram bot interface in `bot.py`
- FastAPI backend in `api.py`
- Static web dashboard in `static/`
- x402/GOAT Testnet 3 payment flow placeholders
- AI arbitration, disputes, reputation, history, leaderboard, and stats

## Features

- Create escrow jobs with a description, USDC amount, and deadline
- Generate demo x402 payment order details
- Submit completed work for AI review
- Score submissions from 1 to 10 using Groq
- Return payment verdicts: `APPROVE`, `PARTIAL`, or `REJECT`
- Track job status: `open`, `completed`, `refunded`, `disputed`, and `expired`
- Raise disputes for completed or refunded jobs
- Track freelancer reputation and leaderboard rankings
- Serve a browser dashboard from the `static/` folder

## Project Structure

```text
ESCROW-BOT/
├── api.py              # FastAPI backend and static file server
├── bot.py              # Telegram bot
├── requirements.txt    # Python dependencies
├── Procfile            # Worker process for deployment
├── static/
│   ├── index.html      # Web dashboard
│   ├── app.js          # Frontend logic
│   └── style.css       # Dashboard styles
└── .env                # Local secrets, ignored by git
```

## Requirements

- Python 3.10+
- Telegram bot token from BotFather
- Groq API key
- Optional GOAT/x402 API credentials for live payment actions

Install dependencies:

```bash
pip install -r requirements.txt
```

If you run the FastAPI backend locally, you may also need:

```bash
pip install fastapi uvicorn pydantic
```

## Environment Variables

Create a `.env` file in the project root:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
GROQ_API_KEY=your_groq_api_key
GOATX402_API_URL=your_x402_api_url
GOATX402_API_KEY=your_x402_api_key
```

`GOATX402_API_URL` and `GOATX402_API_KEY` are only required for real release/refund calls from the Telegram bot. The backend currently creates demo payment order details.

## Running Locally

Start the FastAPI backend:

```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

Open the web dashboard:

```text
http://localhost:8000
```

Start the Telegram bot in a second terminal:

```bash
python bot.py
```

The Telegram bot expects the API to be running at:

```text
http://localhost:8000
```

## Telegram Commands

```text
/start
/newjob
/submitwork <job_id>
/checkstatus <job_id>
/myjobs
/history
/reputation <username>
/leaderboard
/dispute <job_id>
```

## API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/api/jobs` | List all jobs |
| `POST` | `/api/jobs` | Create a new escrow job |
| `GET` | `/api/jobs/{job_id}` | Get a job by ID |
| `PATCH` | `/api/jobs/{job_id}` | Update job fields |
| `POST` | `/api/jobs/{job_id}/submit` | Submit work for AI evaluation |
| `POST` | `/api/jobs/{job_id}/dispute` | Raise a dispute for re-evaluation |
| `GET` | `/api/reputation/{username}` | Get freelancer reputation |
| `GET` | `/api/leaderboard` | Get top freelancers |
| `GET` | `/api/history/{username}` | Get jobs for a user |
| `GET` | `/api/stats` | Get dashboard stats |

## Example Job Request

```json
{
  "description": "Write a 500 word blog post about AI escrow.",
  "amount": "5",
  "deadline": "2",
  "client": "alice"
}
```

## Example Work Submission

```json
{
  "work": "Completed blog post text goes here.",
  "freelancer": "bob"
}
```

## Deployment

The included `Procfile` runs the Telegram bot as a worker:

```text
worker: python bot.py
```

For a hosted deployment, run both services:

- API/web service: `uvicorn api:app --host 0.0.0.0 --port $PORT`
- Bot worker: `python bot.py`

Update `API_BASE` in `bot.py` if the API is not running at `http://localhost:8000`.

## Important Notes

- Job and reputation data are stored in memory, so they reset whenever the server restarts.
- The backend x402 order creation is currently demo-mode and returns a testnet explorer/payment address.
- The bot includes release/refund helper calls for x402, but they require valid `GOATX402_API_URL` and `GOATX402_API_KEY`.
- Keep `.env` private. It should not be committed.
