# Loom script: FirstRung, about 5 minutes

## Before you record

- Open these tabs in order:
  1. https://jobs-beige-seven.vercel.app
  2. `/jobs`
  3. One job page from an Adzuna job
  4. `/dashboard`, already logged in
  5. `/docs`
  6. Your repo's GitHub Actions page
- Open https://jobs-l8jk.onrender.com/api/meta once, about 2 minutes before you start. This wakes up the API so the first page loads fast.
- Close other tabs and hide your email and any notifications.

---

## 1. Hello (0:00 – 0:20)

**Show:** the home page.

**Say:**
> "Hi, I'm Mohammad. This is FirstRung, a job board just for freshers in India. Every night it collects jobs from official job APIs, an AI labels each job, and students can search them here. Let me show you how it works."

## 2. Home page (0:20 – 0:40)

**Show:** the three number tiles, then the role buttons.

**Say:**
> "These numbers are live from the API: about 257 fresher jobs from 130 companies. Below, you can jump straight to a role like software or support."

## 3. Search and filters (0:40 – 1:30)

**Show:** `/jobs`.

**Do:**
1. Type "intern" and press Search.
2. Pick Job type: Internship, then City: Bengaluru.
3. Point at the address bar.

**Say:**
> "Here is the search. You can filter by role, city, work mode, job type and experience. Each option shows how many jobs it has. The filters are saved in the link, so you can share a search with a friend. Each card shows the AI tags and where the job came from, like 'via Adzuna' or 'via Greenhouse'."

## 4. A job page (1:30 – 2:05)

**Show:** click one job card.

**Say:**
> "This is one job. The tags at the top, like internship, onsite and no experience needed, were added by the AI. Apply always takes you to the employer's own page, we never copy the job. Adzuna only shares a short preview of each job, so we say that clearly and link to the full posting."

**Do:** hover over the "Read the full description" link.

## 5. Login and dashboard (2:05 – 2:35)

**Do:** click Save on the job, then open `/dashboard`.

**Say:**
> "Students can log in with email or Google. Saved jobs show up here, and every job you clicked Apply on is listed with the time, so you can keep track."

## 6. Phone view (2:35 – 2:50)

**Do:** press F12, turn on the phone view, then reload `/jobs`.

**Say:**
> "It works on phones too. The filters fold behind one button so the jobs come first."

**Do:** turn off phone view.

## 7. How it's built (2:50 – 3:40)

**Show:** `/docs`, then scroll to Architecture.

**Say:**
> "Now, how it works inside. There are four parts. A Python worker runs every night on GitHub Actions. It fetches jobs and saves them to a Postgres database on Neon. A Spring Boot API on Render reads that data. And this Next.js website on Vercel shows it. Everything runs on free plans."

**Do:** scroll to the Daily run steps.

**Say:**
> "Each night the worker fetches jobs, keeps only India fresher jobs, removes duplicates, and skips jobs that haven't changed, so we don't pay for the AI twice. Then it tags the new jobs and hides old ones."

**Do:** scroll to AI tagging, then Prompts.

**Say:**
> "For tagging, it tries Gemini first, then Groq, then OpenRouter, and simple rules last. Here's the exact prompt. The AI can only answer from a fixed list of values, so it can't invent a city."

## 8. Cost and real runs (3:40 – 4:15)

**Show:** the Cost section, then Run history.

**Say:**
> "We pay zero dollars, but we count every token. At Claude Haiku prices, 1,000 jobs would cost about 17 cents. This table shows the last real nightly runs, read live from the database."

**Do:** switch to the GitHub Actions tab and show one green run for about 5 seconds.

## 9. What I learned (4:15 – 4:45)

**Show:** `/docs`, the "What I found" section.

**Say:**
> "Three things I learned. One: company career pages have very few fresher jobs in India. I checked about 1,200 boards and only around 45 had any, so Adzuna brings most of the jobs. Two: the free AI tiers were good enough. Three: my own rule wrongly marked 22 'Graduate Engineer Trainee' jobs as internships. The AI was right, so I fixed the rule and added a test."

## 10. Close (4:45 – 5:00)

**Show:** the "Limits and next steps" section.

**Say:**
> "Next, I'd add more job APIs like Jooble and finish the accuracy check on 50 hand-labelled jobs. The full write-up is on the docs page. Thanks for watching!"

---

## Tips

- Speak slowly. If you're running long, skip section 6 (phone view).
- Move your mouse to whatever you're talking about.
- If a page loads slowly, keep talking. Don't wait in silence.
- If you're short on time, practise once with this script open on a second screen.
