# ForBot Simulation Server

This small FastAPI server provides an HTTP API to create and run in-memory simulations from the existing project.

Quick start (recommended to use a virtualenv):

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Start the server (from project root):

```bash
uvicorn backend.server:app --reload
```

Frontend (Vite + React)

A minimal Vite React frontend is included under `frontend/`. It talks to the backend API at `http://localhost:8000` by default.

Install frontend deps and start the dev server:

```bash
cd frontend
npm install
npm run dev
```

Open the app at `http://localhost:5173` and use the UI to create and list simulations.

Endpoints

- POST /simulations -> create a new simulation, returns {id}
- GET /simulations -> list simulations with basic counts
- POST /simulations/{id}/generate_users {"num_users": N} -> generate N users
- POST /simulations/{id}/advance {"hours": N} -> advance the simulation N hours
- GET /simulations/{id} -> summary counts
- GET /simulations/{id}/forum -> forum metadata
- GET /simulations/{id}/users -> all users (serialized)
- GET /simulations/{id}/threads -> threads
- GET /simulations/{id}/posts -> posts
- GET /simulations/{id}/posts/{post_id} -> single post

Notes

- Simulations are stored in memory for the running server process. Persist or snapshot them externally if you need long-term storage.
- The simulation uses the `Simulation` class in `main.py`. Creating a simulation will import `main.py` and read `wow.txt` (so ensure `wow.txt` is present).