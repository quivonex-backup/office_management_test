# Local venv vs Docker Commands

The main commands you normally use locally inside your venv are:

| Purpose           | Local / venv command                  | Docker equivalent                                                 |
|---------          |----------------------                 |--------------------                                               |
| Run server        | `python manage.py runserver`          | `docker compose up -d`                                            |
| Install package   | `pip install package_name`            | See note below                                                    |
| Make migrations   | `python manage.py makemigrations`     | `docker compose exec backend python manage.py makemigrations`     |
| Migrate           | `python manage.py migrate`            | `docker compose exec backend python manage.py migrate`            |
| Create app        | `python manage.py startapp app_name`  | `docker compose exec backend python manage.py startapp app_name`  |
| Create superuser  | `python manage.py createsuperuser`    | `docker compose exec backend python manage.py createsuperuser`    |
| Django shell      | `python manage.py shell`              | `docker compose exec backend python manage.py shell`              |

---


### Install package ###

1. Add the package to requirements.txt:
celery==5.6.3

2. Rebuild and start Docker:
docker compose up --build -d






## Will local venv changes reflect in Docker?

### Code/files: **YES**.

Because you have:

```yaml
volumes:
  - .:/app
if you run locally:

bash
python manage.py startapp notifications
it creates files in your project:

text
apps/
└── notifications/
Those files are visible to Docker immediately because they're actual project files.

Same for:

models.py

views.py

serializers.py

migrations/

Installed Python packages: NO
If your venv is activated and you run:

bash
pip install celery
that installs Celery into:

text
venv
└── site-packages
    └── celery
It does not install Celery inside your Docker image/container.

You need to update:

bash
pip freeze > requirements.txt
and then rebuild Docker:

bash
docker compose up --build -d
Then Docker executes:

dockerfile
RUN pip install --no-cache-dir -r requirements.txt
and Celery becomes installed in the Docker image.

So remember:
text
Change Python/Django code
        ↓
Docker sees it automatically ✅

Create files/apps/migrations
        ↓
Docker sees them automatically ✅

pip install in local venv
        ↓
Docker DOES NOT see package ❌
        ↓
pip freeze > requirements.txt
        ↓
docker compose up --build -d
        ↓
Docker now has package ✅





# 1. Validate the Compose configuration
docker compose config

# 2. Build the Django image
docker compose build

# 3. Run Django migrations against your existing database
docker compose run --rm web python manage.py migrate

# 4. Start all services
docker compose up -d

# 5. Check container status
docker compose ps

# 6. View application logs
docker compose logs -f web celery_worker celery_beat

# 7. Verify that Celery and attendance scheduling work

docker compose exec celery_worker celery -A config inspect ping
docker compose logs --tail=100 celery_beat
docker compose logs --tail=100 celery_worker

Task	                                Command
Start everything	                docker compose up -d
Stop everything	                        docker compose down
Rebuild after dependency changes	docker compose up --build -d
View all logs	                        docker compose logs -f
Restart Django	                        docker compose restart web
Open Django shell	                docker compose exec web python manage.py shell
Run migrations	                        docker compose exec web python manage.py migrate
Check container status	                docker compose ps




>> mkdir app/chatbot 
>> python manage.py startapp chatbot app/chatbot  


wsl
sudo service redis-server start
redis-cli ping   # should now return PONG
sudo service redis-server status