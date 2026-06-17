# Python + React Authentication System (JWT + 2FA)

This project implements a complete authentication flow using:

- **JWT access + refresh tokens**
- **Two-Factor Authentication (2FA)** with TOTP & QR codes
- **Secure cookie-based refresh token handling**
- **React Context for client-side token management**
- **Route protection** via React Router

---

## Stack

| Part     | Tech                                          |
| -------- | --------------------------------------------- |
| Frontend | React 19, React Router, Vite, Tailwind CSS    |
| Backend  | Python 3.12, FastAPI, SQLAlchemy, SQLite       |
| Auth     | PyJWT (access + refresh), pyotp (2FA/TOTP)    |

---

## Features

- Signup & Login with JWT
- Access token stored in memory
- Refresh token stored in HttpOnly cookie
- 2FA (opt-in) with OTP QR code via pyotp
- Protected routes via React Router and Auth Context
- Password reset (with token, no email service)

---

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 18+

### Backend Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

The backend runs on `http://localhost:5002`.

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend runs on `http://localhost:5173`.

---

## Architecture

The frontend (React/Vite) communicates directly with the Python FastAPI backend.
CORS is configured to allow the frontend origin with credentials support.

```
React (Vite :5173) ──HTTP──> FastAPI (:5002) ──SQLAlchemy──> SQLite
```
