import os
import json
import httpx
import random
import string
import asyncio
from groq import Groq
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
API_BASE = "http://localhost:8000"
API_URL = os.getenv("GOATX402_API_URL")
API_KEY = os.getenv("GOATX402_API_KEY")

# ─────────────────────────────────────────
# x402 helpers
# ─────────────────────────────────────────
def create_order(amount: str, job_id: str, description: str) -> dict:
    try:
        resp = httpx.post(
            f"{API_BASE}/api/jobs",
            json={
                "description": description,
                "amount": amount,
                "deadline": "2",
                "client": "telegram_bot"
            },
            timeout=10.0
        )
        data = resp.json()
        return {
            "order_id": data.get("order_id", job_id),
            "payment_url": data.get("payment_url", f"https://pay.testnet3.goat.network/{job_id}"),
            "pay_to_address": data.get("pay_to_address", "")
        }
    except Exception as e:
        print(f"Order creation error: {str(e)}")
        return {
            "order_id": f"order_{job_id}",
            "payment_url": f"https://pay.testnet3.goat.network/{job_id}",
            "pay_to_address": ""
        }

def release_payment(order_id: str):
    try:
        httpx.post(f"{API_URL}/api/v1/orders/{order_id}/complete", headers={"X-Api-Key": API_KEY}, timeout=10.0)
    except Exception as e:
        print(f"Release payment error: {str(e)}")

def refund_payment(order_id: str):
    try:
        httpx.post(f"{API_URL}/api/v1/orders/{order_id}/cancel", headers={"X-Api-Key": API_KEY}, timeout=10.0)
    except Exception as e:
        print(f"Refund payment error: {str(e)}")

# ─────────────────────────────────────────
# AI Evaluation
# ─────────────────────────────────────────
def evaluate_work_with_ai(job_description: str, submitted_work: str) -> dict:
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{
            "role": "user",
            "content": f"""You are a fair freelance work arbitrator.

Job Description: {job_description}

Submitted Work: {submitted_work}

Evaluate the submitted work strictly and fairly.
Respond ONLY in this JSON format with no extra text:
{{
  "score": <1-10>,
  "payment_percentage": <0-100>,
  "reasoning": "<brief explanation>",
  "verdict": "<APPROVE | PARTIAL | REJECT>"
}}

Score guide:
- 9-10: Excellent, pay 100%
- 7-8: Good, pay 85%
- 5-6: Acceptable, pay 60%
- 3-4: Poor, pay 30%
- 1-2: Unacceptable, refund client"""
        }],
        temperature=0.1
    )
    return json.loads(response.choices[0].message.content)

# ─────────────────────────────────────────
# Deadline checker (background task)
# ─────────────────────────────────────────
async def check_deadlines(app):
    while True:
        try:
            resp = httpx.get(f"{API_BASE}/api/jobs")
            jobs = resp.json().get("jobs", {})
            import time
            now = int(time.time())
            for job_id, job in jobs.items():
                deadline_at = job.get("deadline_at", 0)
                status = job.get("status", "")
                if status == "open" and deadline_at > 0:
                    time_left = deadline_at - now
                    # Warn 30 min before deadline
                    if 0 < time_left <= 1800:
                        print(f"[DEADLINE WARNING] Job {job_id} expires in {time_left//60} minutes")
                    # Expired
                    elif time_left <= 0:
                        httpx.patch(f"{API_BASE}/api/jobs/{job_id}", json={"status": "expired"})
                        print(f"[EXPIRED] Job {job_id} marked as expired")
        except Exception as e:
            print(f"Deadline check error: {e}")
        await asyncio.sleep(60)  # Check every minute

# ─────────────────────────────────────────
# /start
# ─────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to AI Escrow Arbitrator 🔐\n\n"
        "Trustless freelance payments powered by x402 + Groq AI\n\n"
        "Commands:\n"
        "/newjob — Post a job and lock payment\n"
        "/submitwork <job_id> — Submit completed work\n"
        "/checkstatus <job_id> — Check escrow status\n"
        "/myjobs — See all your jobs\n"
        "/history — View your job history\n"
        "/reputation <username> — Check freelancer reputation\n"
        "/leaderboard — Top rated freelancers\n"
        "/dispute <job_id> — Raise a dispute"
    )

# ─────────────────────────────────────────
# /newjob
# ─────────────────────────────────────────
async def new_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 Create a New Job\n\n"
        "Send details in this format:\n\n"
        "JOB: <description>\n"
        "AMOUNT: <USDC amount>\n"
        "DEADLINE: <hours>\n\n"
        "Example:\n"
        "JOB: Write a 500 word blog post about AI\n"
        "AMOUNT: 5\n"
        "DEADLINE: 2"
    )
    context.user_data['awaiting'] = 'new_job'

# ─────────────────────────────────────────
# /submitwork
# ─────────────────────────────────────────
async def submit_work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /submitwork <job_id>")
        return

    job_id = context.args[0]

    try:
        resp = httpx.get(f"{API_BASE}/api/jobs/{job_id}")
        job = resp.json()
        if "error" in job:
            await update.message.reply_text("❌ Job not found.")
            return
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
        return

    if job['status'] != 'open':
        await update.message.reply_text(f"❌ Job is already {job['status']}.")
        return

    await update.message.reply_text(
        f"📤 Submitting work for Job {job_id}\n\n"
        f"Job: {job['description']}\n\n"
        "Send your completed work as the next message:"
    )
    context.user_data['awaiting'] = 'work_submission'
    context.user_data['job_id'] = job_id

# ─────────────────────────────────────────
# /checkstatus
# ─────────────────────────────────────────
async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /checkstatus <job_id>")
        return

    job_id = context.args[0]

    try:
        resp = httpx.get(f"{API_BASE}/api/jobs/{job_id}")
        job = resp.json()
        if "error" in job:
            await update.message.reply_text("❌ Job not found.")
            return
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
        return

    status_emoji = {
        'open': '🟡', 'completed': '✅',
        'refunded': '🔴', 'disputed': '⚖️', 'expired': '⏰'
    }

    await update.message.reply_text(
        f"📊 Job Status\n\n"
        f"ID: {job_id}\n"
        f"Description: {job['description']}\n"
        f"Amount: {job['amount']} USDC\n"
        f"Status: {status_emoji.get(job['status'], '❓')} {job['status']}\n"
        f"Client: @{job['client']}\n"
        + (f"Freelancer: @{job.get('freelancer')}\n" if job.get('freelancer') else "")
        + (f"AI Score: {job.get('score')}/10\n" if job.get('score') else "")
        + (f"Verdict: {job.get('verdict')}\n" if job.get('verdict') else "")
    )

# ─────────────────────────────────────────
# /myjobs
# ─────────────────────────────────────────
async def my_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.effective_user.username or "anonymous"
    try:
        resp = httpx.get(f"{API_BASE}/api/jobs")
        all_jobs = resp.json().get("jobs", {})
        user_jobs = {k: v for k, v in all_jobs.items() if v['client'] == username}
    except Exception as e:
        await update.message.reply_text(f"❌ Could not fetch jobs: {str(e)}")
        return

    if not user_jobs:
        await update.message.reply_text("You have no active jobs.")
        return

    msg = "📋 Your Jobs:\n\n"
    for job_id, job in user_jobs.items():
        status_emoji = {'open': '🟡', 'completed': '✅', 'refunded': '🔴', 'disputed': '⚖️', 'expired': '⏰'}
        msg += f"{status_emoji.get(job['status'], '❓')} {job_id} — {job['description'][:500]}... [{job['status']}]\n"

    await update.message.reply_text(msg)

# ─────────────────────────────────────────
# /history
# ─────────────────────────────────────────
async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.effective_user.username or "anonymous"
    try:
        resp = httpx.get(f"{API_BASE}/api/history/{username}")
        jobs = resp.json().get("history", {})
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
        return

    if not jobs:
        await update.message.reply_text("No job history found.")
        return

    msg = "📝 Your Job History:\n\n"
    for job_id, job in jobs.items():
        status_emoji = {'open': '🟡', 'completed': '✅', 'refunded': '🔴', 'disputed': '⚖️', 'expired': '⏰'}
        msg += (
            f"{status_emoji.get(job['status'], '❓')} {job_id}\n"
            f"   {job['description'][:30]}...\n"
            f"   Amount: {job['amount']} USDC"
        )
        if job.get('score'):
            msg += f" | Score: {job['score']}/10"
        msg += f"\n\n"

    await update.message.reply_text(msg)

# ─────────────────────────────────────────
# /reputation
# ─────────────────────────────────────────
async def reputation_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        username = context.args[0].replace("@", "")
    else:
        username = update.effective_user.username or "anonymous"

    try:
        resp = httpx.get(f"{API_BASE}/api/reputation/{username}")
        data = resp.json()
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
        return

    await update.message.reply_text(
        f"⭐ Reputation: @{username}\n\n"
        f"Level: {data.get('level', 'New')}\n"
        f"Avg Score: {data.get('avg_score', 0)}/10\n"
        f"Total Jobs: {data.get('total_jobs', 0)}\n"
        f"Completed: {data.get('completed', 0)}\n"
        f"Rejected: {data.get('rejected', 0)}\n"
    )

# ─────────────────────────────────────────
# /leaderboard
# ─────────────────────────────────────────
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        resp = httpx.get(f"{API_BASE}/api/leaderboard")
        data = resp.json().get("leaderboard", [])
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
        return

    if not data:
        await update.message.reply_text("No freelancers on leaderboard yet.")
        return

    msg = "🏆 Freelancer Leaderboard\n\n"
    for entry in data:
        msg += (
            f"#{entry['rank']} @{entry['username']} — {entry['level']}\n"
            f"   Avg Score: {entry['avg_score']}/10 | Jobs: {entry['total_jobs']}\n\n"
        )

    await update.message.reply_text(msg)

# ─────────────────────────────────────────
# /dispute
# ─────────────────────────────────────────
async def dispute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /dispute <job_id>")
        return

    job_id = context.args[0]

    try:
        resp = httpx.get(f"{API_BASE}/api/jobs/{job_id}")
        job = resp.json()
        if "error" in job:
            await update.message.reply_text("❌ Job not found.")
            return
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
        return

    if job['status'] not in ['completed', 'refunded']:
        await update.message.reply_text("❌ Can only dispute completed or refunded jobs.")
        return

    await update.message.reply_text(
        f"⚖️ Raising Dispute for Job {job_id}\n\n"
        f"Job: {job['description']}\n"
        f"Current Score: {job.get('score')}/10\n"
        f"Current Verdict: {job.get('verdict')}\n\n"
        "Explain your reason for disputing:"
    )
    context.user_data['awaiting'] = 'dispute'
    context.user_data['dispute_job_id'] = job_id

# ─────────────────────────────────────────
# Handle all text messages
# ─────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    awaiting = context.user_data.get('awaiting')
    text = update.message.text
    username = update.effective_user.username or "anonymous"

    # ── Creating a new job ──
    if awaiting == 'new_job':
        lines = text.strip().split('\n')
        try:
            job_desc = next(l.replace('JOB:', '').strip() for l in lines if l.startswith('JOB:'))
            amount = next(l.replace('AMOUNT:', '').strip() for l in lines if l.startswith('AMOUNT:'))
            deadline = next(l.replace('DEADLINE:', '').strip() for l in lines if l.startswith('DEADLINE:'))
        except StopIteration:
            await update.message.reply_text("❌ Wrong format. Please follow the template.")
            return

        job_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        await update.message.reply_text("⏳ Creating escrow order on x402...")

        try:
            order = create_order(amount, job_id, job_desc)
            order_id = order.get("order_id", job_id)
            payment_url = order.get("payment_url", "")
            pay_to = order.get("pay_to_address", "")

            await update.message.reply_text(
                f"✅ Escrow Created on x402!\n\n"
                f"Job ID: {job_id}\n"
                f"Description: {job_desc}\n"
                f"Amount: {amount} USDC\n"
                f"Deadline: {deadline} hours\n"
                f"Order ID: {order_id}\n\n"
                f"Payment Link:\n{payment_url}\n\n"
                + (f"Pay To:\n{pay_to}\n\n" if pay_to else "")
                + f"Share Job ID {job_id} with your freelancer!\n"
                  f"They use: /submitwork {job_id}"
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to create order: {str(e)}")

        context.user_data['awaiting'] = None

    # ── Submitting work ──
    elif awaiting == 'work_submission':
        job_id = context.user_data.get('job_id')

        try:
            resp = httpx.get(f"{API_BASE}/api/jobs/{job_id}")
            job = resp.json()
        except Exception as e:
            await update.message.reply_text(f"❌ Error fetching job: {str(e)}")
            return

        await update.message.reply_text("🤖 AI is evaluating your work...")

        try:
            result = evaluate_work_with_ai(job['description'], text)

            httpx.patch(f"{API_BASE}/api/jobs/{job_id}", json={
                "score": result['score'],
                "status": "completed" if result['verdict'] != 'REJECT' else "refunded",
                "verdict": result['verdict'],
                "reasoning": result['reasoning'],
                "freelancer": username
            })

            # Update reputation
            httpx.get(f"{API_BASE}/api/reputation/{username}")

            verdict_emoji = {'APPROVE': '✅', 'PARTIAL': '⚡', 'REJECT': '❌'}
            amount = job['amount']

            if result['verdict'] == 'APPROVE':
                release_payment(job['order_id'])
                payment_action = f"✅ {amount} USDC released to freelancer!"
            elif result['verdict'] == 'PARTIAL':
                release_payment(job['order_id'])
                payment_action = f"⚡ Partial payment ({result['payment_percentage']}%) released!"
            else:
                refund_payment(job['order_id'])
                payment_action = "🔴 Payment refunded to client"

            await update.message.reply_text(
                f"🏛 AI Arbitration Result\n\n"
                f"Job: {job['description']}\n"
                f"Score: {result['score']}/10\n"
                f"Verdict: {verdict_emoji.get(result['verdict'], '❓')} {result['verdict']}\n"
                f"Payment: {result['payment_percentage']}% of {amount} USDC\n"
                f"= {float(amount) * result['payment_percentage'] / 100:.2f} USDC\n\n"
                f"Reasoning: {result['reasoning']}\n\n"
                f"{payment_action}\n\n"
                f"Your reputation has been updated! Check with /reputation"
            )

        except Exception as e:
            await update.message.reply_text(f"❌ Evaluation failed: {str(e)}")

        context.user_data['awaiting'] = None
        context.user_data['job_id'] = None

    # ── Dispute reason ──
    elif awaiting == 'dispute':
        job_id = context.user_data.get('dispute_job_id')

        await update.message.reply_text("⚖️ AI is re-evaluating your dispute...")

        try:
            resp = httpx.post(
                f"{API_BASE}/api/jobs/{job_id}/dispute",
                json={"reason": text, "raised_by": username}
            )
            result = resp.json()

            if "error" in result:
                await update.message.reply_text(f"❌ {result['error']}")
                return

            outcome_emoji = "✅" if result['dispute_outcome'] == 'UPHELD' else "❌"

            await update.message.reply_text(
                f"⚖️ Dispute Result\n\n"
                f"Outcome: {outcome_emoji} {result['dispute_outcome']}\n"
                f"Explanation: {result['dispute_explanation']}\n\n"
                f"New Score: {result['new_score']}/10\n"
                f"New Verdict: {result['new_verdict']}\n"
                f"New Reasoning: {result['new_reasoning']}\n\n"
                f"Payment Released: {result['payment_released']} USDC"
            )

        except Exception as e:
            await update.message.reply_text(f"❌ Dispute failed: {str(e)}")

        context.user_data['awaiting'] = None
        context.user_data['dispute_job_id'] = None

# ─────────────────────────────────────────
# Button callbacks
# ─────────────────────────────────────────
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("lock_"):
        job_id = query.data.replace("lock_", "")
        await query.edit_message_text(
            f"✅ Payment locked for Job {job_id}!\n\n"
            f"Share with freelancer: /submitwork {job_id}"
        )

# ─────────────────────────────────────────
# Main
# ─────────────────────────────────────────
def main():
    application = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("newjob", new_job))
    application.add_handler(CommandHandler("submitwork", submit_work))
    application.add_handler(CommandHandler("checkstatus", check_status))
    application.add_handler(CommandHandler("myjobs", my_jobs))
    application.add_handler(CommandHandler("history", history))
    application.add_handler(CommandHandler("reputation", reputation_cmd))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("dispute", dispute))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 AI Escrow Arbitrator is running...")
    application.run_polling()

if __name__ == "__main__":
    main()