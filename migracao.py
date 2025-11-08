# MIGRACAO PARA ADICIONAR nivel_acesso
def migrar_adicionar_nivel_acesso():
    with app.app_context():
        import sqlite3
        conn = sqlite3.connect('instance/igreja.db')
        cursor = conn.cursor()
        
        # Verifica se a coluna já existe
        cursor.execute("PRAGMA table_info(user)")
        colunas = [col[1] for col in cursor.fetchall()]
        
        if 'nivel_acesso' not in colunas:
            print("Adicionando coluna 'nivel_acesso'...")
            cursor.execute("ALTER TABLE user ADD COLUMN nivel_acesso INTEGER DEFAULT 2")
            conn.commit()
            print("Coluna adicionada com sucesso!")
        else:
            print("Coluna 'nivel_acesso' já existe.")
        
        conn.close()

# RODE ESTA FUNÇÃO UMA VEZ
if __name__ == '__main__':
    migrar_adicionar_nivel_acesso()