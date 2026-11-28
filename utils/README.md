# Superuser Credentials for this local project 

python manage.py createsuperuser

Username: admin                         
Email: sravanfakesinha@gmail.com
Password: Sravan@123
Password (again): Sravan@123






# Project Management System — Backend

Backend API for the Project Management System built using **Django** and **Django REST Framework**.

The project uses Docker for a consistent development environment.

---

# 1. Technology Stack

* Python 3.10
* Django 5.2
* Django REST Framework
* MySQL
* JWT Authentication
* Docker
* Docker Compose
* AWS S3 / Django Storages

Planned infrastructure:

* Redis
* Celery
* Celery Beat

---

# 2. Project Structure

```text
project_management/
│
├── office_management/
│   │
│   ├── Dockerfile
│   ├── compose.yml
│   ├── .dockerignore
│   ├── .env
│   ├── .gitignore
│   ├── requirements.txt
│   ├── manage.py
│   │
│   ├── config/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
│   │
│   └── app/
│       ├── accounts/
│       ├── projects/
│       └── clients/
│       └── ...
│
├── venv/
│
└── README.md
```

### Important Directory

Most Docker and Django commands documented below should be executed from:

```text
D:\S_Projects\Backend_Pr\project_management\office_management
```

This is because this directory contains:

```text
compose.yml
Dockerfile
manage.py
requirements.txt
.env
```

Example:

```powershell
cd D:\S_Projects\Backend_Pr\project_management\office_management
```

---

# 3. Docker Architecture

Current development architecture:

```text
                    Windows Host
                         │
          ┌──────────────┴──────────────┐
          │                             │
     Docker Desktop                 MySQL
          │                         :3306
          │                             ▲
          ▼                             │
 project_backend                       │
          │                             │
          │ Django                     │
          │ Python 3.10                 │
          │                             │
          └── host.docker.internal ─────┘
                   │
                   ▼
                Port 8000
                   │
                   ▼
        http://localhost:8000
```

MySQL currently runs directly on the Windows host.

The Django container therefore connects to MySQL using:

```text
host.docker.internal
```

instead of:

```text
localhost
```

The normal `.env` can still contain:

```env
DB_HOST=localhost
```

because `compose.yml` overrides `DB_HOST` for the Docker container.

---

# 4. Docker Files

## Dockerfile

The Dockerfile creates the Django backend image.

```dockerfile
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

The MySQL development libraries are required because the project uses:

```text
mysqlclient
```

---

## compose.yml

Docker Compose is the recommended way to run the project during development.

```yaml
services:

  backend:
    build: .
    container_name: project_backend

    command: python manage.py runserver 0.0.0.0:8000

    volumes:
      - .:/app

    ports:
      - "8000:8000"

    env_file:
      - .env

    environment:
      DB_HOST: host.docker.internal
```

The volume:

```yaml
volumes:
  - .:/app
```

connects the local source code to the container.

Therefore, changes to files such as:

```text
views.py
models.py
serializers.py
urls.py
permissions.py
services.py
```

are immediately visible inside Docker.

Django's development server will normally reload automatically.

---

# 5. First-Time Docker Setup

Install and start Docker Desktop.

Verify Docker:

```powershell
docker --version
```

Check that the Docker Engine is running:

```powershell
docker info
```

Move to the backend directory:

```powershell
cd D:\S_Projects\Backend_Pr\project_management\office_management
```

Build and start the project:

```powershell
docker compose up --build
```

Or start it in the background:

```powershell
docker compose up --build -d
```

The API will be available at:

```text
http://localhost:8000
```

---

# 6. Normal Daily Development

## Start Project

After opening the laptop:

1. Start Docker Desktop.
2. Open VS Code.
3. Open the terminal.
4. Move to the backend directory:

```powershell
cd D:\S_Projects\Backend_Pr\project_management\office_management
```

Start Docker:

```powershell
docker compose up
```

For background/detached mode:

```powershell
docker compose up -d
```

Detached mode keeps the terminal free while the containers continue running.

---

## Stop Project

If running attached with:

```powershell
docker compose up
```

press:

```text
Ctrl + C
```

Then:

```powershell
docker compose down
```

If running in detached mode:

```powershell
docker compose down
```

---

## Restart Backend

```powershell
docker compose restart backend
```

---

## Check Running Services

```powershell
docker compose ps
```

---

## View Django Logs

```powershell
docker compose logs -f backend
```

Press:

```text
Ctrl + C
```

to stop following the logs.

This does not necessarily stop the backend container when it is running in detached mode.

---

# 7. Django Development Commands

Run Django commands through the `backend` Docker Compose service.

## Create New App

From:

D:\S_Projects\Backend_Pr\project_management\office_management>

run:

mkdir app\app_name

Then:

docker compose exec backend python manage.py startapp app_name app/app_name

## Make Migrations

After changing database models:

```powershell
docker compose exec backend python manage.py makemigrations
```

For a specific app:

```powershell
docker compose exec backend python manage.py makemigrations accounts
```

Example:

```powershell
docker compose exec backend python manage.py makemigrations projects
```

---

## Apply Migrations

```powershell
docker compose exec backend python manage.py migrate
```

---

## Check Migrations

```powershell
docker compose exec backend python manage.py showmigrations
```

---

## Create Superuser

```powershell
docker compose exec backend python manage.py createsuperuser
```

Example values:

```text
Username: admin
Email: admin@example.com
Password: <strong-password>
```

Never store real passwords in the repository or README.

---

## Django Shell

```powershell
docker compose exec backend python manage.py shell
```

Exit:

```python
exit()
```

---

## Enter Container Linux Shell

```powershell
docker compose exec backend sh
```

Inside the container:

```bash
python --version
```

List files:

```bash
ls
```

The application should be located at:

```text
/app
```

Exit the container shell:

```bash
exit
```

---

# 8. Code Changes

Because the project directory is mounted using:

```yaml
volumes:
  - .:/app
```

normal source-code changes do **not** require rebuilding Docker.

Examples:

```text
views.py
serializers.py
permissions.py
urls.py
services.py
models.py
settings.py
```

Normal workflow:

```text
Edit file
   ↓
Save
   ↓
Docker sees change
   ↓
Django auto-reloads
```

No Docker rebuild is normally required.

---

# 9. Model Changes

If the database structure changes:

```text
Edit models.py
      ↓
Save
      ↓
makemigrations
      ↓
migrate
```

Commands:

```powershell
docker compose exec backend python manage.py makemigrations
```

Then:

```powershell
docker compose exec backend python manage.py migrate
```

A Docker rebuild is normally not required.

---

# 10. Installing New Python Packages

Python packages used by the application must ultimately be recorded in:

```text
requirements.txt
```

For example, to temporarily install a package inside the running backend container:

```powershell
docker compose exec backend pip install celery
```

Update `requirements.txt`:

```powershell
docker compose exec backend pip freeze > requirements.txt
```

Then rebuild the Docker image:

```powershell
docker compose up --build
```

For background mode:

```powershell
docker compose up --build -d
```

### Important

A package manually installed only inside a running container can disappear when that container is recreated.

Therefore:

```text
Install package
      ↓
Update requirements.txt
      ↓
Rebuild Docker image
```

---

# 11. When Do I Need to Rebuild?

| Change                      | Action                     |
| --------------------------- | -------------------------- |
| `views.py`                  | No rebuild                 |
| `serializers.py`            | No rebuild                 |
| `urls.py`                   | No rebuild                 |
| `permissions.py`            | No rebuild                 |
| `services.py`               | No rebuild                 |
| Model business logic        | No rebuild                 |
| Model database structure    | Make migrations + migrate  |
| `settings.py`               | Usually no rebuild         |
| `requirements.txt`          | Rebuild                    |
| `Dockerfile`                | Rebuild                    |
| Major `compose.yml` changes | Recreate/restart Compose   |
| `.env` changes              | Recreate/restart container |

Rebuild with:

```powershell
docker compose up --build
```

or:

```powershell
docker compose up --build -d
```

---

# 12. Docker Command Cheat Sheet

| Situation            | Command                                                        |
| -------------------- | -------------------------------------------------------------- |
| Start project        | `docker compose up`                                            |
| Start in background  | `docker compose up -d`                                         |
| Stop project         | `docker compose down`                                          |
| Rebuild + start      | `docker compose up --build`                                    |
| Rebuild + background | `docker compose up --build -d`                                 |
| Check services       | `docker compose ps`                                            |
| Django logs          | `docker compose logs -f backend`                               |
| Restart Django       | `docker compose restart backend`                               |
| Make migrations      | `docker compose exec backend python manage.py makemigrations`  |
| Migrate              | `docker compose exec backend python manage.py migrate`         |
| Show migrations      | `docker compose exec backend python manage.py showmigrations`  |
| Create superuser     | `docker compose exec backend python manage.py createsuperuser` |
| Django shell         | `docker compose exec backend python manage.py shell`           |
| Container shell      | `docker compose exec backend sh`                               |

---

# 13. Docker Image vs Container vs Service

## Image

A Docker image is the packaged application blueprint.

Example:

```text
Python 3.10
+
System Libraries
+
requirements.txt
+
Django
+
Application
```

The Dockerfile defines how this image is built.

---

## Container

A container is a running instance of an image.

```text
Dockerfile
    ↓
Image
    ↓
Container
    ↓
Running Django
```

---

## Service

A service is a component defined in `compose.yml`.

Currently:

```yaml
services:
  backend:
```

So the project currently has one Docker Compose service:

```text
backend
    ↓
Django container
    ↓
Django development server
```

Future architecture may contain:

```text
Docker Compose
│
├── backend
│   └── Django
│
├── db
│   └── MySQL
│
├── redis
│   └── Redis
│
├── celery
│   └── Celery Worker
│
└── celery-beat
    └── Scheduled Tasks
```

---

# 14. Raw Docker Commands

Docker Compose is the recommended development workflow.

These commands are mainly useful for understanding/debugging Docker directly.

## Build Image Manually

```powershell
docker build -t project-management-backend .
```

Check images:

```powershell
docker images
```

---

## Run Container Manually

```powershell
docker run --name project_backend --env-file .env -e DB_HOST=host.docker.internal -p 8000:8000 project-management-backend
```

---

## Check Running Containers

```powershell
docker ps
```

Check all containers:

```powershell
docker ps -a
```

---

## Stop Manual Container

```powershell
docker stop project_backend
```

---

## Start Existing Manual Container

```powershell
docker start project_backend
```

Attach to its output:

```powershell
docker start -a project_backend
```

---

## Remove Manual Container

```powershell
docker rm -f project_backend
```

Do not normally mix the manual `docker run` workflow with the Docker Compose workflow.

For normal development, use Docker Compose.

---

# 15. Setting Up the Project on Another Computer

## Prerequisites

Currently required:

* Git
* Docker Desktop
* MySQL

Python and a Python virtual environment are not required when running the backend through Docker.

---

## Clone Repository

```powershell
git clone <repository-url>
```

Move into the backend:

```powershell
cd project_management/office_management
```

---

## Configure Environment Variables

Create:

```text
.env
```

from the project's environment-variable template when available.

Configure values such as:

```env
SECRET_KEY=your-secret-key

DB_NAME=project_management
DB_USER=root
DB_PASSWORD=your-password
DB_HOST=localhost
DB_PORT=3306
```

Never commit the real `.env` file.

---

## Create MySQL Database

Create the database specified by:

```env
DB_NAME=project_management
```

The exact database name must match the environment configuration.

---

## Build and Start Backend

```powershell
docker compose up --build -d
```

---

## Apply Database Migrations

```powershell
docker compose exec backend python manage.py migrate
```

---

## Create Admin User

```powershell
docker compose exec backend python manage.py createsuperuser
```

---

## Open Application

```text
http://localhost:8000
```

---

## Stop Application

```powershell
docker compose down
```

---

# 16. Quick Setup Summary

For an existing developer:

```powershell
cd office_management

docker compose up -d
```

Start coding.

When finished:

```powershell
docker compose down
```

For a fresh clone:

```powershell
git clone <repository-url>

cd project_management/office_management

docker compose up --build -d

docker compose exec backend python manage.py migrate

docker compose exec backend python manage.py createsuperuser
```

Then access:

```text
http://localhost:8000
```

---

# 17. Planned Docker Architecture

The current setup Dockerizes the Django backend while MySQL runs on the host machine.

The planned complete development environment is:

```text
                    Docker Compose
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
       Backend           MySQL           Redis
       Django              DB             Cache
          │                                │
          │                                │
          └────────────┐          ┌────────┘
                       ▼          ▼
                         Celery
                         Worker
                           │
                           ▼
                      Celery Beat
```

This will allow the complete backend environment to be started through Docker Compose.
