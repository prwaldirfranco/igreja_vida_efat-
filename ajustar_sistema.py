import os
from app import app, db, Configuracao
from sqlalchemy import text

def coluna_existe(tabela, coluna):
    insp = db.inspect(db.engine)
    colunas = [c['name'] for c in insp.get_columns(tabela)]
    return coluna in colunas

def tabela_existe(tabela):
    insp = db.inspect(db.engine)
    return tabela in insp.get_table_names()

def executar_alter(comando):
    try:
        db.session.execute(text(comando))
        db.session.commit()
        print(f"[OK] Executado: {comando}")
    except Exception as e:
        print(f"[ERRO] {comando} → {e}")

def atualizar_configuracao():
    print("\n=== VERIFICANDO TABELA CONFIGURACAO ===")

    if not tabela_existe("configuracao"):
        print("[INFO] Tabela 'configuracao' ainda não existe. Será criada em migrations normais.")
        return

    # Criar coluna provisao_extras
    if not coluna_existe("configuracao", "provisao_extras"):
        executar_alter(
            "ALTER TABLE configuracao ADD COLUMN provisao_extras FLOAT DEFAULT 0.0"
        )

    # Criar coluna salario_medio
    if not coluna_existe("configuracao", "salario_medio"):
        executar_alter(
            "ALTER TABLE configuracao ADD COLUMN salario_medio FLOAT DEFAULT 2000.0"
        )

def criar_admin_padrao():
    from app import User
    print("\n=== VERIFICANDO ADMINISTRADOR PADRÃO ===")

    admin_email = "combave@gmail.com"
    existe = User.query.filter_by(email=admin_email).first()

    if existe:
        print("Administrador já existe.")
    else:
        from werkzeug.security import generate_password_hash
        admin = User(
            nome="Secretaria Vida Efatá",
            email=admin_email,
            senha=generate_password_hash("combave2025"),
            nivel_acesso=1,
            is_secretaria=True,
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        print("Administrador criado com sucesso!")

def main():
    with app.app_context():
        print("\n====================================")
        print("  AJUSTE COMPLETO DO SISTEMA EFATÁ")
        print("====================================\n")

        atualizar_configuracao()
        criar_admin_padrao()

        print("\n✓ Ajustes concluídos com sucesso!")
        print("Agora você pode rodar normalmente: flask run")
        print("--------------------------------------------")

if __name__ == "__main__":
    main()
