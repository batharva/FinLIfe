# 💸 FinLife — Personal Finance Management

<p align="center">
  <strong>Take control of your money. Build better financial habits.</strong>
</p>

<p align="center">
  <a href="https://iatharvab-finlife.streamlit.app/">
    <img src="https://img.shields.io/badge/Live%20Demo-Open%20FinLife-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" alt="Live Demo"/>
  </a>
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/Streamlit-App-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" alt="Streamlit"/>
  <img src="https://img.shields.io/badge/Supabase-Backend-3FCF8E?style=for-the-badge&logo=supabase&logoColor=white" alt="Supabase"/>
</p>

**FinLife** is a personal finance management web application built with Python, Streamlit, and Supabase. It helps users organize their finances, track income and expenses, manage budgets, plan financial goals, and monitor their financial progress from one place.

🌐 **Live Application:** [iatharvab-finlife.streamlit.app](https://iatharvab-finlife.streamlit.app/)

---

## 📌 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Technology Stack](#-technology-stack)
- [Application Architecture](#-application-architecture)
- [Database Design](#-database-design)
- [Getting Started](#-getting-started)
- [Environment Configuration](#-environment-configuration)
- [Database Setup](#-database-setup)
- [Deployment](#-deployment)
- [Security](#-security)
- [Future Improvements](#-future-improvements)
- [Contributing](#-contributing)
- [License](#-license)

## 🚀 Overview

Managing personal finances can become complicated when transactions, accounts, budgets, savings, and investments are tracked separately.

FinLife brings these activities together in a centralized application designed to make financial tracking more organized and accessible.

The project combines an interactive Streamlit interface with Supabase authentication and a PostgreSQL database to provide persistent, user-specific financial data.

### Project Goals

- Simplify personal income and expense tracking.
- Improve visibility into spending habits.
- Organize finances using accounts and categories.
- Help users create budgets and financial goals.
- Track assets, liabilities, and investment scenarios.
- Provide a foundation for future financial analytics.

## ✨ Features

### 💰 Financial Tracking
- Record income, expenses, investments, transfers, and refunds.
- Organize transactions using financial categories.
- Associate transactions with individual accounts.
- Store transaction dates, payment methods, and notes.
- Support recurring transaction records.

### 📊 Budget Management
- Create and manage monthly budgets.
- Associate budgets with expense categories.
- Configure budget warning thresholds.
- Track spending against budget limits.

### 🎯 Financial Goal Planning
- Create goals for savings, education, travel, retirement, and other objectives.
- Define target amounts and target dates.
- Track allocated amounts and goal contributions.
- Organize goals by priority and status.

### 📈 Investment Planning
- Create investment scenarios.
- Configure initial investments and monthly contributions.
- Set investment horizons and assumed returns.
- Compare conservative, moderate, and aggressive risk profiles.

### 🏦 Accounts and Net Worth
- Organize bank accounts, cash, wallets, credit cards, and other account types.
- Record opening balances.
- Track assets and liabilities.
- Maintain valuation history for net-worth analysis.

### 👤 User Accounts and Preferences
- Authenticate users through Supabase.
- Maintain user-specific profiles.
- Store currency and theme preferences.
- Configure needs, wants, and savings allocation percentages.

> Feature availability depends on the deployed application version and its database configuration.

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| Python | Application logic and backend operations |
| Streamlit | Interactive web application interface |
| Supabase Auth | User authentication |
| PostgreSQL | Relational database |
| Supabase Data API | Database access from the application |
| SQL | Schema, constraints, indexes, triggers, and access policies |
| Git and GitHub | Version control and source code management |
| Streamlit Community Cloud | Application hosting |

## 🏗️ Application Architecture

FinLife uses a layered architecture:

```text
                 ┌──────────────────────┐
                 │       User           │
                 └──────────┬───────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │   Streamlit UI       │
                 │  app.py / views      │
                 └──────────┬───────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │   Service / Data     │
                 │   Access Layer       │
                 └──────────┬───────────┘
                            │
                  ┌─────────┴─────────┐
                  ▼                   ▼
        ┌────────────────┐  ┌────────────────┐
        │ Supabase Auth  │  │ Supabase Data  │
        │ Authentication │  │ API / Postgres │
        └────────────────┘  └────────────────┘
```

The Streamlit application handles the user interface, while Supabase provides authentication and persistent database storage.

## 🗄️ Database Design

The database schema is defined in [`database/schema.sql`](database/schema.sql).

| Table | Purpose |
|---|---|
| `profiles` | User preferences and profile information |
| `accounts` | Financial account records |
| `categories` | Transaction and financial classifications |
| `transactions` | Income, expense, transfer, and investment records |
| `budgets` | Monthly budget allocations |
| `financial_goals` | Financial targets and progress |
| `goal_contributions` | Contributions and withdrawals associated with goals |
| `investment_plans` | Investment scenario assumptions |
| `assets_and_liabilities` | Asset and liability valuations |
| `recurring_transactions` | Scheduled or recurring financial records |

The schema also defines relationships, indexes, update triggers, profile creation on signup, and Row Level Security (RLS) policies.

## ⚙️ Getting Started

### Prerequisites

Before running FinLife locally, make sure you have:

- Python installed.
- Git installed.
- A Supabase project.
- Access to the project's Supabase URL and publishable or legacy `anon` API key.

### 1. Clone the Repository

```bash
git clone https://github.com/batharva/FinLife.git
cd FinLife
```

Replace the repository URL if your actual GitHub repository uses a different owner or name.

### 2. Create a Virtual Environment

**Windows:**

```bash
python -m venv .venv
.venv\Scripts\activate
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Secrets

Create a file named `.streamlit/secrets.toml` in the project root.

```toml
SUPABASE_URL = "https://YOUR-PROJECT-REF.supabase.co"
SUPABASE_ANON_KEY = "YOUR_PUBLISHABLE_OR_ANON_KEY"
APP_URL = "http://localhost:8501"
GOOGLE_LOGIN_ENABLED = "0"
```

Replace the placeholders with the correct values from your Supabase project.

Use `GOOGLE_LOGIN_ENABLED = "1"` only after Google OAuth has been configured, if you intend to use Google sign-in.

**Never commit your real secrets to GitHub.**

### 5. Set Up the Database

1. Open your Supabase project.
2. Navigate to **SQL Editor**.
3. Open `database/schema.sql` from the repository.
4. Execute the complete schema script in the correct project.
5. Verify that the required tables and RLS policies were created successfully.

Back up existing data before applying schema changes to an existing database. The script's `CREATE TABLE IF NOT EXISTS` statements do not automatically add missing columns to tables that already exist.

### 6. Run the Application

```bash
streamlit run app.py
```

Streamlit will display a local URL, typically:

```text
http://localhost:8501
```

Open the URL in your browser to use the application.

## 🔐 Environment Configuration

FinLife uses Streamlit secrets for configuration.

| Variable | Description |
|---|---|
| `SUPABASE_URL` | URL of the Supabase project |
| `SUPABASE_ANON_KEY` | Publishable key or legacy `anon` key |
| `APP_URL` | Base URL of the deployed or local application |
| `GOOGLE_LOGIN_ENABLED` | Enables or disables Google login according to the application code |

The variable `SUPABASE_ANON_KEY` is retained for compatibility with the application's configuration. A modern Supabase publishable key can be used if the application passes it correctly to the Supabase client.

Do not use a Supabase secret key or legacy `service_role` key as the client-side application key.

## ☁️ Deployment

FinLife is deployed on Streamlit Community Cloud.

**Live application:** [Open FinLife](https://iatharvab-finlife.streamlit.app/)

To deploy your own instance:

1. Push the project to a GitHub repository.
2. Open [Streamlit Community Cloud](https://share.streamlit.io/).
3. Connect your GitHub account.
4. Select the repository and branch.
5. Set the main file path to `app.py`.
6. Configure the required secrets in the app settings.
7. Deploy the application.
8. Configure the Supabase Site URL and allowed redirect URLs to match the deployed application.

## 🔒 Security

Because FinLife stores personal financial information, security is an important part of its design.

- Use Supabase authentication for user identity.
- Enable RLS on all tables containing user-specific financial data.
- Restrict database policies using the authenticated user's ID.
- Never expose database secret keys in client code or public repositories.
- Store credentials in Streamlit secrets or local environment configuration.
- Avoid sharing authentication URLs containing access or refresh tokens.
- Validate database permissions and user isolation before using real financial data.

RLS policies must be tested carefully; enabling RLS alone does not guarantee that every table has the correct access rules.

## 🗺️ Future Improvements

Potential areas for future development include:

- Enhanced financial dashboards and spending visualizations.
- Monthly and yearly financial reports.
- CSV import and export.
- Automated recurring transaction processing.
- More detailed savings and investment projections.
- Improved mobile responsiveness.
- Additional financial insights and spending analysis.
- Expanded testing and error handling.

## 🤝 Contributing

Contributions, bug reports, and suggestions are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Make your changes.
4. Test the application locally.
5. Submit a pull request describing your changes.

For major changes, open an issue first to discuss the proposed improvement.

## 📄 License

No license has been specified here. Add a `LICENSE` file to your repository if you want to define how others may use, modify, and distribute this project.

---

<p align="center">
  Built with ❤️ using Python, Streamlit, and Supabase.
  <br/>
  <a href="https://iatharvab-finlife.streamlit.app/">Try FinLife Live</a>
</p>
