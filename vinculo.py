# vinculo.py
from app import db  # importa o SQLAlchemy do seu app Flask
from app import Usuario, Membro  # importa suas classes/modelos reais

def vincular_usuario_membro(usuario_id, membro_id):
    usuario = Usuario.query.get(usuario_id)
    membro = Membro.query.get(membro_id)

    if not usuario:
        print(f"Usuário com ID {usuario_id} não encontrado.")
        return
    if not membro:
        print(f"Membro com ID {membro_id} não encontrado.")
        return

    # aqui fazemos o vínculo
    usuario.membro_id = membro.id  # ou o campo que você usa para vincular
    db.session.commit()
    print(f"Usuário {usuario.nome} vinculado ao membro {membro.nome} com sucesso!")

if __name__ == "__main__":
    # exemplo: vincular usuário 1 ao membro 2
    vincular_usuario_membro(1, 2)
