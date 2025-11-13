from app import db, create_initial_data

# Recria todas as tabelas (APAGA tudo anterior!)
db.drop_all()
db.create_all()
create_initial_data()
print("✅ Banco recriado com sucesso!")
