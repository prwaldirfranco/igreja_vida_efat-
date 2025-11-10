from app import app, db, Membro

with app.app_context():
    # DELETE TODOS OS MEMBROS
    num_deletados = Membro.query.delete()
    db.session.commit()
    print(f"✅ LIMPOU {num_deletados} membros do banco!")
    print("Banco pronto para novo CSV!")

exit()