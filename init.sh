echo ====MIGRATING [START]====
python manage.py migrate
echo ====MIGRATING [END]====

echo ====CREATING ADMIN [START]====
python manage.py initadmin
echo ====CREATING ADMIN [END]====

echo ====RUNNING [START]====
gunicorn traApp.wsgi:application --bind 0.0.0.0:9999

