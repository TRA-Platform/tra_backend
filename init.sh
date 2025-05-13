echo ====INSTALLING DEPENDENCIES [START]====
playwright install
echo ====INSTALLING DEPENDENCIES [END]====
echo ====MIGRATING [START]====
python manage.py migrate
echo ====MIGRATING [END]====

echo ====CREATING ADMIN [START]====
python manage.py initadmin
echo ====CREATING ADMIN [END]====

echo ====RUNNING [START]====
gunicorn traApp.wsgi:application --bind 0.0.0.0:9999 --workers 4 --timeout 600

