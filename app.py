import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField, PasswordField, SubmitField, FloatField, SelectField,
    TextAreaField, DateField, BooleanField, IntegerField
)
from wtforms.validators import DataRequired, Email, Optional
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from dotenv import load_dotenv
from sqlalchemy import func, or_
from functools import wraps
import pandas as pd
import pdfkit
import csv
from io import StringIO, BytesIO

# ---- CONFIGURAÇÕES ----
load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "superseguro123")
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'app.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Inicializar extensões
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Faça login para acessar esta página."
login_manager.login_message_category = "info"

# ---- MODELOS ----
class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)
    nivel_acesso = db.Column(db.Integer, default=2)  # 1=Admin, 2=Secretária, 3=Financeiro, 4=Visualizador
    is_secretaria = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<User {self.email} - Nível {self.nivel_acesso}>'

class Membro(db.Model):
    __tablename__ = 'membro'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100))
    telefone = db.Column(db.String(20))
    celular = db.Column(db.String(20))
    endereco = db.Column(db.String(200))
    cep = db.Column(db.String(10))
    bairro = db.Column(db.String(50))
    cidade = db.Column(db.String(50), default="São Paulo")
    estado = db.Column(db.String(2), default="SP")
    data_nascimento = db.Column(db.Date)
    estado_civil = db.Column(db.String(20))
    conjuge = db.Column(db.String(100))
    filhos = db.Column(db.Integer, default=0)
    batizado = db.Column(db.Boolean, default=False)
    data_batismo = db.Column(db.Date)
    ministerio = db.Column(db.String(100))
    foto = db.Column(db.String(100), default='default.jpg')  # CORRIGIDO: apenas uma vez
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    ativo = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<Membro {self.nome}>'

class Transacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50))
    categoria = db.Column(db.String(100))
    valor = db.Column(db.Float)
    metodo = db.Column(db.String(20))
    data = db.Column(db.DateTime, default=datetime.utcnow)
    membro_id = db.Column(db.Integer, db.ForeignKey('membro.id'), nullable=True)
    membro = db.relationship('Membro', backref='transacoes')
    is_fixo = db.Column(db.Boolean, default=False)

class Evento(db.Model):
    __tablename__ = 'evento'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    data = db.Column(db.Date, nullable=False)
    imagem = db.Column(db.String(200))

class Ministerio(db.Model):
    __tablename__ = 'ministerio'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    lider = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f'<Ministerio {self.nome}>'

# ---- LOGIN ----
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---- DECORADORES DE PERMISSÃO ----
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if (not current_user.is_authenticated or 
            current_user.nivel_acesso is None or 
            current_user.nivel_acesso != 1):
            flash("Acesso negado. Apenas Admin.", "danger")
            return redirect(url_for('secretaria'))
        return f(*args, **kwargs)
    return decorated_function

def secretaria_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if (not current_user.is_authenticated or 
            current_user.nivel_acesso is None or 
            current_user.nivel_acesso > 2):
            flash("Acesso negado. Apenas Secretária/Admin.", "danger")
            return redirect(url_for('secretaria'))
        return f(*args, **kwargs)
    return decorated_function

def financeiro_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.nivel_acesso > 3:
            flash("Acesso negado. Apenas Financeiro ou superior.", "danger")
            return redirect(url_for('secretaria'))
        return f(*args, **kwargs)
    return decorated_function

# ---- FORMULÁRIOS ----
class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()], render_kw={"autocomplete": "username"})
    senha = PasswordField("Senha", validators=[DataRequired()], render_kw={"autocomplete": "current-password"})
    submit = SubmitField("Entrar")

class UsuarioForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    senha = PasswordField("Senha", validators=[DataRequired()])
    nivel_acesso = SelectField("Nível de Acesso", choices=[
        (1, "Admin (acesso total)"),
        (2, "Secretária (membros + eventos)"),
        (3, "Financeiro (apenas financeiro)"),
        (4, "Visualizador (apenas relatórios)")
    ], coerce=int, validators=[DataRequired()])
    submit = SubmitField("Criar Usuário")

class MembroForm(FlaskForm):
    nome = StringField("Nome Completo", validators=[DataRequired()])
    email = StringField("E-mail", validators=[Email()])
    telefone = StringField("Telefone Fixo")
    celular = StringField("Celular (WhatsApp)", validators=[DataRequired()])
    cep = StringField("CEP")
    endereco = StringField("Endereço")
    bairro = StringField("Bairro")
    cidade = StringField("Cidade")
    estado = StringField("Estado")
    data_nascimento = DateField("Data de Nascimento", format="%Y-%m-%d")
    estado_civil = SelectField("Estado Civil", choices=[
        ("", "Selecione..."),
        ("solteiro", "Solteiro(a)"),
        ("casado", "Casado(a)"),
        ("viuvo", "Viúvo(a)"),
        ("divorciado", "Divorciado(a)")
    ])
    conjuge = StringField("Nome do Cônjuge")
    filhos = IntegerField("Quantidade de Filhos", default=0)
    batizado = BooleanField("É Batizado(a)?")
    data_batismo = DateField("Data do Batismo", format="%Y-%m-%d")
    ministerio = StringField("Ministério que Participa")
    foto = FileField("Foto", validators=[FileAllowed(['jpg', 'png', 'jpeg', 'gif'])])
    ativo = BooleanField("Membro Ativo", default=True)
    submit = SubmitField("Salvar Membro")

class TransacaoForm(FlaskForm):
    data_transacao = DateField("Data da Transação", format="%Y-%m-%d", validators=[DataRequired()], default=datetime.now().date())
    tipo = SelectField("Tipo", choices=[
        ("dizimo", "Dízimo"),
        ("oferta", "Oferta"),
        ("doacao", "Doação"),
        ("despesa", "Despesa")
    ])
    categoria = StringField("Categoria (ex: culto, aluguel)", validators=[DataRequired()])
    valor = FloatField("Valor", validators=[DataRequired()])
    metodo = SelectField("Método", choices=[
        ("dinheiro", "Dinheiro"),
        ("pix", "Pix"),
        ("cartao", "Cartão")
    ])
    membro_id = SelectField("Membro (opcional)", coerce=int, validators=[Optional()])
    is_fixo = SelectField("Fixo Mensal?", choices=[
        (0, "Não"),
        (1, "Sim")
    ], coerce=int)
    submit = SubmitField("Registrar")

class EventoForm(FlaskForm):
    titulo = StringField("Título", validators=[DataRequired()])
    descricao = TextAreaField("Descrição", validators=[DataRequired()])
    data = DateField("Data", format="%Y-%m-%d", validators=[DataRequired()])
    imagem = FileField("Imagem", validators=[FileAllowed(['jpg', 'png', 'jpeg', 'gif'])])
    submit = SubmitField("Salvar")

class MinisterioForm(FlaskForm):
    nome = StringField("Nome do Ministério", validators=[DataRequired()])
    lider = StringField("Líder", validators=[DataRequired()])
    descricao = TextAreaField("Descrição", validators=[DataRequired()])
    submit = SubmitField("Salvar")

# ---- CONTEXT PROCESSOR ----
@app.context_processor
def inject_year():
    return {'current_year': datetime.now().year}

# ---- ROTAS PÚBLICAS ----
@app.route('/')
def index():
    eventos = Evento.query.order_by(Evento.data.asc()).limit(3).all()
    return render_template('public/public_index.html', eventos=eventos)

@app.route('/eventos')
def eventos():
    eventos = Evento.query.order_by(Evento.data.desc()).all()
    return render_template('public/eventos.html', eventos=eventos)

@app.route('/ministerios')
def ministerios():
    ministerios = Ministerio.query.order_by(Ministerio.nome).all()
    return render_template('public/ministerios.html', ministerios=ministerios)

@app.route('/sobre')
def sobre():
    return render_template('public/sobre.html')

@app.route('/contato')
def contato():
    return render_template('public/contato.html')

# ---- LOGIN / LOGOUT ----
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.senha, form.senha.data):
            login_user(user)
            flash("Login realizado com sucesso!", "success")
            return redirect(url_for("secretaria"))
        flash("Credenciais inválidas!", "danger")
    return render_template('auth/login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logout realizado com sucesso.", "info")
    return redirect(url_for('index'))

# ---- SECRETARIA ----
@app.route('/secretaria')
@login_required
def secretaria():
    if not current_user.is_authenticated or current_user.nivel_acesso is None or current_user.nivel_acesso > 2:
        flash("Acesso restrito.", "danger")
        return redirect(url_for('index'))

    membros_count = Membro.query.count()
    transacoes_total = db.session.query(func.sum(Transacao.valor)).scalar() or 0
    eventos = Evento.query.order_by(Evento.data.desc()).limit(5).all()

    return render_template('secretaria/secretaria_dashboard.html',
                           membros_count=membros_count,
                           transacoes_total=transacoes_total,
                           eventos=eventos)

# ---- USUÁRIOS ----
@app.route('/secretaria/usuarios/novo', methods=['GET', 'POST'])
@admin_required
@login_required
def novo_usuario():
    form = UsuarioForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash("Este email já está cadastrado.", "danger")
            return redirect(url_for('novo_usuario'))

        hashed = generate_password_hash(form.senha.data)
        user = User(
            nome=form.nome.data,
            email=form.email.data,
            senha=hashed,
            nivel_acesso=form.nivel_acesso.data,
            is_secretaria=(form.nivel_acesso.data <= 2)
        )
        db.session.add(user)
        db.session.commit()
        flash("Usuário criado com sucesso!", "success")
        return redirect(url_for('secretaria'))

    return render_template('secretaria/usuarios_form.html', form=form)

@app.route('/secretaria/usuarios')
@admin_required
@login_required
def listar_usuarios():
    usuarios = User.query.order_by(User.nivel_acesso, User.nome).all()
    return render_template('secretaria/usuarios_list.html', usuarios=usuarios)

# ---- MINISTÉRIOS ----
@app.route('/secretaria/ministerios')
@secretaria_required
@login_required
def listar_ministerios():
    ministerios = Ministerio.query.order_by(Ministerio.nome).all()
    return render_template('secretaria/ministerios_list.html', ministerios=ministerios)

@app.route('/secretaria/ministerios/novo', methods=['GET', 'POST'])
@secretaria_required
@login_required
def novo_ministerio():
    form = MinisterioForm()
    if form.validate_on_submit():
        ministerio = Ministerio(
            nome=form.nome.data,
            lider=form.lider.data,
            descricao=form.descricao.data
        )
        db.session.add(ministerio)
        db.session.commit()
        flash("Ministério criado com sucesso!", "success")
        return redirect(url_for('listar_ministerios'))
    return render_template('secretaria/ministerios_form.html', form=form, title="Novo Ministério")

@app.route('/secretaria/ministerios/editar/<int:id>', methods=['GET', 'POST'])
@secretaria_required
@login_required
def editar_ministerio(id):
    ministerio = Ministerio.query.get_or_404(id)
    form = MinisterioForm(obj=ministerio)
    if form.validate_on_submit():
        ministerio.nome = form.nome.data
        ministerio.lider = form.lider.data
        ministerio.descricao = form.descricao.data
        db.session.commit()
        flash("Ministério atualizado!", "success")
        return redirect(url_for('listar_ministerios'))
    return render_template('secretaria/ministerios_form.html', form=form, title="Editar Ministério")

@app.route('/secretaria/ministerios/excluir/<int:id>')
@secretaria_required
@login_required
def excluir_ministerio(id):
    ministerio = Ministerio.query.get_or_404(id)
    db.session.delete(ministerio)
    db.session.commit()
    flash("Ministério excluído.", "info")
    return redirect(url_for('listar_ministerios'))

# ---- MEMBROS ----
@app.route('/membros')
@secretaria_required
@login_required
def listar_membros():
    query = request.args.get('q', '').strip()
    ministerios = Ministerio.query.order_by(Ministerio.nome).all()

    if query:
        search = f"%{query}%"
        membros = Membro.query.filter(
            or_(
                Membro.nome.ilike(search),
                Membro.celular.ilike(search),
                Membro.email.ilike(search)
            )
        ).order_by(Membro.nome).all()
    else:
        membros = Membro.query.order_by(Membro.nome).all()

    return render_template('secretaria/membros_list.html', membros=membros, ministerios=ministerios)

@app.route('/membro/editar/<int:id>', methods=['GET', 'POST'])
@secretaria_required
@login_required
def editar_membro(id):
    membro = Membro.query.get_or_404(id)
    ministerios = Ministerio.query.order_by(Ministerio.nome).all()

    if request.method == 'POST':
        membro.nome = request.form['nome']
        membro.email = request.form['email']
        membro.celular = request.form['celular']
        membro.estado_civil = request.form['estado_civil']

        min_id = request.form.get('ministerio_id')
        if min_id:
            ministerio = Ministerio.query.get(min_id)
            membro.ministerio = ministerio.nome if ministerio else ''
        else:
            membro.ministerio = ''

        if 'foto' in request.files:
            file = request.files['foto']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                file.save(os.path.join('static/fotos_membros', filename))
                membro.foto = filename

        db.session.commit()
        flash("Membro atualizado com sucesso!", "success")
        return redirect(url_for('listar_membros'))

    return redirect(url_for('listar_membros'))

@app.route('/membro/novo', methods=['GET', 'POST'])
@secretaria_required
@login_required
def novo_membro():
    form = MembroForm()
    if form.validate_on_submit():
        filename = None
        if form.foto.data:
            filename = secure_filename(form.foto.data.filename)
            form.foto.data.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        membro = Membro(
            nome=form.nome.data,
            email=form.email.data,
            telefone=form.telefone.data,
            celular=form.celular.data,
            cep=form.cep.data,
            endereco=form.endereco.data,
            bairro=form.bairro.data,
            cidade=form.cidade.data,
            estado=form.estado.data,
            data_nascimento=form.data_nascimento.data,
            estado_civil=form.estado_civil.data,
            conjuge=form.conjuge.data,
            filhos=form.filhos.data,
            batizado=form.batizado.data,
            data_batismo=form.data_batismo.data,
            ministerio=form.ministerio.data,
            foto=filename,
            ativo=form.ativo.data
        )
        db.session.add(membro)
        db.session.commit()
        flash("Membro cadastrado com sucesso!", "success")
        return redirect(url_for('listar_membros'))

    return render_template('secretaria/membros_form.html', form=form)

@app.route('/membro/excluir/<int:id>', methods=['POST'])
@secretaria_required
@login_required
def excluir_membro(id):
    membro = Membro.query.get_or_404(id)
    db.session.delete(membro)
    db.session.commit()
    flash(f"Membro {membro.nome} excluído!", "info")
    return redirect(url_for('listar_membros'))

@app.route('/membros/importar', methods=['GET', 'POST'])
@secretaria_required
@login_required
def importar_membros():
    if request.method == 'POST':
        file = request.files['csv_file']
        if file and file.filename.endswith('.csv'):
            stream = StringIO(file.stream.read().decode("UTF-8"))
            csv_reader = csv.DictReader(stream)
            count = 0
            for row in csv_reader:
                try:
                    celulares = [c.strip() for c in row.get('celular', '').split('|') if c.strip()]
                    celular = celulares[0] if celulares else ''

                    dn = row.get('data_nascimento', '')
                    data_nasc = datetime.strptime(dn, '%d/%m/%Y') if dn and len(dn) == 10 else None

                    dbat = row.get('data_batismo', '')
                    data_bat = datetime.strptime(dbat, '%d/%m/%Y') if dbat and len(dbat) == 10 else None

                    membro = Membro(
                        nome=row.get('nome', '').strip(),
                        email=row.get('email', '').strip(),
                        celular=celular,
                        data_nascimento=data_nasc,
                        estado_civil=row.get('estado_civil', '').strip().lower(),
                        batizado=row.get('batizado', 'nao').lower() == 'sim',
                        data_batismo=data_bat,
                        ministerio=row.get('ministerio', '').strip(),
                        endereco=row.get('endereco', '').strip(),
                        cep=row.get('cep', '').strip(),
                        bairro=row.get('bairro', '').strip(),
                        cidade=row.get('cidade', 'Macae').strip(),
                        estado=row.get('estado', 'RJ').strip(),
                        conjuge=row.get('conjuge', '').strip(),
                        ativo=True
                    )
                    db.session.add(membro)
                    count += 1
                except Exception as e:
                    print(f"Erro na linha: {row} → {e}")
            db.session.commit()
            flash(f"{count} membros importados com sucesso!", "success")
            return redirect(url_for('listar_membros'))

    return render_template('secretaria/importar_membros.html')

# ---- FINANCEIRO ----
@app.route('/financeiro', methods=['GET', 'POST'])
@financeiro_required
@login_required
def financeiro():
    form = TransacaoForm()
    form.membro_id.choices = [(0, '-- Sem membro --')] + [(m.id, m.nome) for m in Membro.query.order_by(Membro.nome).all()]

    mes = request.args.get('mes', datetime.now().strftime('%Y-%m'))

    entradas = Transacao.query.filter(
        Transacao.tipo.in_(['dizimo', 'oferta', 'doacao']),
        func.strftime('%Y-%m', Transacao.data) == mes
    ).all()
    total_entradas = sum(t.valor for t in entradas)

    saidas = Transacao.query.filter(
        Transacao.tipo == 'despesa',
        func.strftime('%Y-%m', Transacao.data) == mes
    ).all()
    total_saidas = sum(t.valor for t in saidas)

    saldo = total_entradas - total_saidas

    fixos = Transacao.query.filter(Transacao.is_fixo == True, Transacao.tipo == 'despesa').all()
    total_fixos = sum(f.valor for f in fixos)
    saldo_final = saldo - total_fixos

    meses_grafico = []
    saldos_grafico = []
    for i in range(5, -1, -1):
        data_mes = (datetime.now() - timedelta(days=30*i)).strftime('%Y-%m')
        entradas_mes = sum(t.valor for t in Transacao.query.filter(
            Transacao.tipo.in_(['dizimo', 'oferta', 'doacao']),
            func.strftime('%Y-%m', Transacao.data) == data_mes
        ).all())
        saidas_mes = sum(t.valor for t in Transacao.query.filter(
            Transacao.tipo == 'despesa',
            func.strftime('%Y-%m', Transacao.data) == data_mes
        ).all())
        saldo_mes = entradas_mes - saidas_mes - total_fixos
        meses_grafico.append((datetime.now() - timedelta(days=30*i)).strftime('%b/%Y'))
        saldos_grafico.append(round(saldo_mes, 2))

    if form.validate_on_submit():
        t = Transacao(
            data=form.data_transacao.data,
            tipo=form.tipo.data,
            categoria=form.categoria.data,
            valor=form.valor.data,
            metodo=form.metodo.data,
            membro_id=form.membro_id.data if form.membro_id.data != 0 else None,
            is_fixo=bool(form.is_fixo.data)
        )
        db.session.add(t)
        db.session.commit()
        flash(f"Transação de R$ {form.valor.data:.2f} registrada para {form.data_transacao.data.strftime('%d/%m/%Y')}!", "success")
        return redirect(url_for('financeiro', mes=mes))

    transacoes = Transacao.query.filter(
        func.strftime('%Y-%m', Transacao.data) == mes
    ).order_by(Transacao.data.desc()).all()

    return render_template('secretaria/financeiro.html',
                           form=form,
                           transacoes=transacoes,
                           total_entradas=total_entradas,
                           total_saidas=total_saidas,
                           saldo=saldo,
                           total_fixos=total_fixos,
                           saldo_final=saldo_final,
                           mes=mes,
                           meses_grafico=meses_grafico,
                           saldos_grafico=saldos_grafico)

@app.route('/financeiro/editar/<int:id>', methods=['GET', 'POST'])
@financeiro_required
@login_required
def editar_transacao(id):
    transacao = Transacao.query.get_or_404(id)
    if request.method == 'POST':
        transacao.data = datetime.strptime(request.form['data_transacao'], '%Y-%m-%d')
        transacao.tipo = request.form['tipo']
        transacao.categoria = request.form['categoria']
        transacao.valor = float(request.form['valor'])
        transacao.metodo = request.form['metodo']
        transacao.is_fixo = bool(int(request.form['is_fixo']))
        db.session.commit()
        flash("Transação atualizada!", "success")
        return redirect(url_for('financeiro', mes=request.args.get('mes', datetime.now().strftime('%Y-%m'))))
    return redirect(url_for('financeiro'))

@app.route('/financeiro/excluir/<int:id>', methods=['POST'])
@financeiro_required
@login_required
def excluir_transacao(id):
    transacao = Transacao.query.get_or_404(id)
    db.session.delete(transacao)
    db.session.commit()
    flash("Transação excluída!", "info")
    return redirect(url_for('financeiro', mes=request.args.get('mes', datetime.now().strftime('%Y-%m'))))

# ---- EXPORTAÇÃO ----
@app.route('/exportar/pdf')
@financeiro_required
@login_required
def exportar_pdf():
    mes = request.args.get('mes', datetime.now().strftime('%Y-%m'))
    tipo = request.args.get('tipo', 'todos')

    query = Transacao.query
    if mes:
        query = query.filter(func.strftime('%Y-%m', Transacao.data) == mes)
    if tipo != 'todos':
        query = query.filter(Transacao.tipo == tipo)

    transacoes = query.order_by(Transacao.data.desc()).all()
    total_geral = sum(t.valor for t in transacoes)

    html = render_template('relatorios/pdf_financeiro.html',
                           transacoes=transacoes,
                           total_geral=total_geral,
                           mes=mes)

    caminho_wk = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
    config = pdfkit.configuration(wkhtmltopdf=caminho_wk)
    pdf = pdfkit.from_string(html, False, configuration=config)

    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=financeiro_{mes}.pdf'
    return response

@app.route('/exportar/excel')
@financeiro_required
@login_required
def exportar_excel():
    mes = request.args.get('mes', datetime.now().strftime('%Y-%m'))
    tipo = request.args.get('tipo', 'todos')

    query = Transacao.query
    if mes:
        query = query.filter(func.strftime('%Y-%m', Transacao.data) == mes)
    if tipo != 'todos':
        query = query.filter(Transacao.tipo == tipo)

    transacoes = query.order_by(Transacao.data.desc()).all()

    data = [{
        'Data': t.data.strftime('%d/%m/%Y'),
        'Tipo': t.tipo.title(),
        'Categoria': t.categoria,
        'Método': t.metodo.title(),
        'Membro': t.membro.nome if t.membro else '-',
        'Valor': t.valor
    } for t in transacoes]

    df = pd.DataFrame(data)
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name=f'financeiro_{mes}.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

# ---- EVENTOS ----
@app.route('/secretaria/eventos/novo', methods=['GET', 'POST'])
@secretaria_required
@login_required
def novo_evento():
    form = EventoForm()
    if form.validate_on_submit():
        filename = None
        if form.imagem.data:
            filename = secure_filename(form.imagem.data.filename)
            form.imagem.data.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        evento = Evento(
            titulo=form.titulo.data,
            descricao=form.descricao.data,
            data=form.data.data,
            imagem=filename
        )
        db.session.add(evento)
        db.session.commit()
        flash("Evento criado com sucesso!", "success")
        return redirect(url_for('secretaria'))

    return render_template('secretaria/eventos_form.html', form=form)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

# ---- INICIALIZAÇÃO ----
def create_initial_data():
    with app.app_context():
        inspector = db.inspect(db.engine)
        if 'user' not in inspector.get_table_names():
            print("Tabela 'user' não existe. Pulando criação de dados.")
            return

        if not User.query.filter_by(email="combave@gmail.com").first():
            hashed = generate_password_hash("combave2025")
            admin = User(
                nome="Secretaria Vida Efatá",
                email="combave@gmail.com",
                senha=hashed,
                nivel_acesso=1,
                is_secretaria=True
            )
            db.session.add(admin)
            db.session.commit()
            print("Admin criado: combave@gmail.com / combave2025")

        if Ministerio.query.count() == 0:
            exemplos = [
                ("Ministério de Louvor", "Bruna Maria", "Adoração sincera."),
                ("Ministério Infantil", "Josilaine", "Crianças no caminho do Senhor."),
                ("Ministério Jovem", "Tatiana e Wendel", "Geração apaixonada por Jesus.")
            ]
            for nome, lider, desc in exemplos:
                m = Ministerio(nome=nome, lider=lider, descricao=desc)
                db.session.add(m)
            db.session.commit()
            print("3 ministérios criados!")

if __name__ == '__main__':
    with app.app_context():
        create_initial_data()
    app.run(debug=True)

