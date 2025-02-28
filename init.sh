echo ====MIGRATING [START]====
python manage.py migrate
echo ====MIGRATING [END]====

echo ====CREATING ADMIN [START]====
python manage.py initadmin
echo ====CREATING ADMIN [END]====

echo ====RUNNING [START]====
python manage.py runserver 0.0.0.0:9999
