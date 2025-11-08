# criar_admin.py
from app import app, db, User
from werkzeug.security import generate_password_hash

with app.app_context():
    db.create_all()  # Cria tabelas se não existirem
    
    if not User.query.filter_by(email="admin@gmail.com").first():
        hashed = generate_password_hash("combave2025")
        admin = User(
            nome="prwaldir",
            email="admin@gmail.com",
            senha=hashed,
            nivel_acesso=1,
            is_secretaria=True
        )
        db.session.add(admin)
        db.session.commit()
        print("USUÁRIO ADMIN CRIADO COM SUCESSO!")
    else:
        print("Usuário já existe.")