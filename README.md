<!-- tutorial run -->
<!-- jangan lupa init venv dulu ya dikadik -->
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows

 uvicorn app.main:app --reload     


 tips bikin model
 edit model / bikin model 
 generate -> alembic revision --autogenerate -m "add email to users"
 Ini akan bikin file di: alembic/versions/xxxx_add_email.py
 Cek file migration
 jalankan file migrationnya alembic upgrade head