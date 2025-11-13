import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, make_response, jsonify
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

# ================================
# CONFIGURAÇÕES
# ================================
load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "superseguro123")
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'app.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
app.config['ALLOWED_EXTENSIONS'] = {
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'tiff', 'heic', 'avif'
}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Inicializar extensões
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Faça login para acessar esta página."
login_manager.login_message_category = "info"

# ================================
# MODELOS
# ================================
class Configuracao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    provisao_extras = db.Column(db.Float, default=0.0)
    salario_medio = db.Column(db.Float, default=2000.0)
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow)

class ConfiguracaoFinanceira(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    meta_dizimistas = db.Column(db.Integer, nullable=False, default=0)
    valor_meta = db.Column(db.Float, nullable=False, default=0.0)
    data_configuracao = db.Column(db.DateTime, default=datetime.utcnow)

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)
    nivel_acesso = db.Column(db.Integer, default=2)
    is_secretaria = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    membro_id = db.Column(db.Integer, db.ForeignKey('membro.id', name="fk_user_membro"), nullable=True)
    membro = db.relationship('Membro', backref='usuario', lazy=True)

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
    foto = db.Column(db.String(100), default='default.jpg')
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='ativo')
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

class CustoFixo(db.Model):
    __tablename__ = 'custos_fixos'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    mes_referencia = db.Column(db.String(7))  # formato: '2025-11'

    def __repr__(self):
        return f"<CustoFixo {self.nome} - R$ {self.valor}>"

# ================================
# LOGIN
# ================================
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ================================
# DECORADORES DE PERMISSÃO
# ================================
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.nivel_acesso != 1:
            flash("Acesso negado. Apenas Admin.", "danger")
            return redirect(url_for('secretaria'))
        return f(*args, **kwargs)
    return decorated_function

def secretaria_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.nivel_acesso > 2:
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

# ================================
# FORMULÁRIOS
# ================================
class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()], render_kw={"autocomplete": "username"})
    senha = PasswordField("Senha", validators=[DataRequired()], render_kw={"autocomplete": "current-password"})
    submit = SubmitField("Entrar")

class UsuarioForm(FlaskForm):
    membro_id = SelectField("Vincular a Membro (opcional)", coerce=int, validators=[Optional()])
    nome = StringField("Nome", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    senha = PasswordField("Senha", validators=[DataRequired()])
    nivel_acesso = SelectField("Nível de Acesso", choices=[
        (1, "Admin (acesso total)"),
        (2, "Secretária (membros + eventos)"),
        (3, "Secretária (membros)"),
        (4, "Financeiro (apenas financeiro)"),
        (5, "Visualizador (apenas relatórios)")
    ], coerce=int, validators=[DataRequired()])
    submit = SubmitField("Criar Usuário")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.membro_id.choices = [(0, "-- Nenhum --")] + [(m.id, m.nome) for m in Membro.query.order_by(Membro.nome).all()]

class MembroForm(FlaskForm):
    nome = StringField("Nome Completo", validators=[DataRequired()])
    email = StringField("E-mail", validators=[Email(), Optional()])
    telefone = StringField("Telefone Fixo")
    celular = StringField("Celular (WhatsApp)", validators=[DataRequired()])
    cep = StringField("CEP")
    endereco = StringField("Endereço")
    bairro = StringField("Bairro")
    cidade = StringField("Cidade")
    estado = StringField("Estado")
    data_nascimento = DateField("Data de Nascimento", format="%Y-%m-%d")
    estado_civil = SelectField("Estado Civil", choices=[
        ('', '--'),
        ('solteiro', 'Solteiro(a)'),
        ('casado', 'Casado(a)'),
        ('viuvo', 'Viúvo(a)'),
        ('divorciado', 'Divorciado(a)')
    ])
    conjuge = StringField("Nome do Cônjuge")
    filhos = IntegerField("Quantidade de Filhos", default=0)
    batizado = BooleanField("É Batizado(a)?")
    data_batismo = DateField("Data do Batismo", format="%Y-%m-%d")
    foto = FileField("Foto", validators=[
        FileAllowed(['jpg','png','jpeg','gif','webp','svg','bmp','tiff','heic','avif'], 'Apenas imagens!')
    ])
    ministerio = SelectField("Ministério", validators=[Optional()])
    status = SelectField("Status", validators=[DataRequired()])

    submit = SubmitField("Salvar Membro")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ministerio.choices = [('', '-- Nenhum --')] + [(m.nome, m.nome) for m in Ministerio.query.order_by(Ministerio.nome).all()]
        self.status.choices = [
            ("ativo", "Ativo"), ("inativo", "Inativo"), ("afastado", "Afastado"),
            ("nao_membro", "Não Membro"), ("visitante", "Visitante")
        ]

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

# ================================
# CONTEXT PROCESSOR
# ================================
@app.context_processor
def inject_year():
    return {'current_year': datetime.now().year}

# ================================
# ROTAS PÚBLICAS
# ================================
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

# ================================
# LOGIN / LOGOUT
# ================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        # Verifica se usuário existe e senha confere
        if user and check_password_hash(user.senha, form.senha.data):
            login_user(user)
            flash("Login realizado com sucesso!", "success")

            # 🔹 Redirecionamentos por nível de acesso
            if user.nivel_acesso <= 3:
                # Admin / Secretaria completa
                return redirect(url_for("secretaria"))
            
            elif user.nivel_acesso == 4:
                # Secretaria restrita (ver lista, cadastrar, editar membros)
                return redirect(url_for("listar_membros"))
            
            elif user.nivel_acesso >= 5:
                # Membro comum (financeiro pessoal)
                return redirect(url_for("financeiro_membro"))
            
            # 🔸 Caso especial: se o nível não se encaixar em nenhum
            else:
                flash("Nível de acesso não reconhecido. Contate o administrador.", "warning")
                return redirect(url_for("logout"))

        # Se não autenticou
        flash("Credenciais inválidas!", "danger")

    # Renderiza tela de login
    return render_template('auth/login.html', form=form)



@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logout realizado com sucesso.", "info")
    return redirect(url_for('index'))

# ================================
# SECRETARIA
# ================================
@app.route('/secretaria')
@login_required
def secretaria():
    if not current_user.is_authenticated or current_user.nivel_acesso > 2:
        flash("Acesso restrito.", "danger")
        return redirect(url_for('index'))

    membros_count = Membro.query.count()
    transacoes_total = db.session.query(func.sum(Transacao.valor)).scalar() or 0
    eventos = Evento.query.order_by(Evento.data.desc()).limit(5).all()

    return render_template('secretaria/secretaria_dashboard.html',
                           membros_count=membros_count,
                           transacoes_total=transacoes_total,
                           eventos=eventos)

@app.route('/custos-fixos/adicionar', methods=['POST'])
@login_required
def adicionar_custo_fixo():
    nome = request.form['nome']
    valor = float(request.form['valor'])
    mes_referencia = request.form.get('mes_referencia', None)
    ativo = 'ativo' in request.form

    novo = CustoFixo(nome=nome, valor=valor, ativo=ativo, mes_referencia=mes_referencia)
    db.session.add(novo)
    db.session.commit()
    flash('Custo fixo adicionado com sucesso!', 'success')
    return redirect(url_for('custos_fixos'))

@app.route('/custos-fixos')
@login_required
def custos_fixos():
    custos = CustoFixo.query.order_by(CustoFixo.nome.asc()).all()
    return render_template('secretaria/custos_fixos.html', custos=custos)

@app.route('/custos-fixos/editar/<int:id>', methods=['POST'])
@login_required
def editar_custo_fixo(id):
    custo = CustoFixo.query.get_or_404(id)
    custo.nome = request.form['nome']
    custo.valor = float(request.form['valor'])
    custo.mes_referencia = request.form.get('mes_referencia', None)
    custo.ativo = 'ativo' in request.form
    db.session.commit()
    flash('Custo fixo atualizado com sucesso!', 'success')
    return redirect(url_for('custos_fixos'))

# ================================
# USUÁRIOS
# ================================
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
            is_secretaria=(form.nivel_acesso.data <= 2),
            is_admin=(form.nivel_acesso.data == 1)
        )
        if form.membro_id.data and form.membro_id.data != 0:
            user.membro_id = form.membro_id.data

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

# ================================
# MINISTÉRIOS
# ================================
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

# ================================
# MEMBROS - LISTAR
# ================================
@app.route('/membros')
@login_required
def listar_membros():
    # Permite níveis 1-4 (admin, secretaria completa e secretaria restrita)
    if current_user.nivel_acesso > 4:
        flash("Acesso negado.", "danger")
        return redirect(url_for('index'))

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


# ================================
# MEMBROS - EDITAR (AJAX)
# ================================
@app.route('/membro/editar/<int:id>', methods=['GET', 'POST'])
@secretaria_required
@login_required
def editar_membro(id):
    membro = Membro.query.get_or_404(id)

    if request.method == 'POST':
        membro.nome = request.form.get('nome')
        membro.email = request.form.get('email') or None
        membro.celular = request.form.get('celular')
        membro.ministerio = request.form.get('ministerio')
        membro.estado_civil = request.form.get('estado_civil') or None
        membro.status = request.form.get('status')

        if 'foto' in request.files and request.files['foto'].filename:
            filename = secure_filename(request.files['foto'].filename)
            request.files['foto'].save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            membro.foto = filename

        membro.ativo = (membro.status == 'ativo')
        db.session.commit()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'membro': {
                    'id': membro.id,
                    'nome': membro.nome,
                    'email': membro.email,
                    'celular': membro.celular,
                    'ministerio': membro.ministerio,
                    'status': membro.status,
                    'foto': membro.foto
                }
            })

        flash("Membro atualizado com sucesso!", "success")
        return redirect(url_for('listar_membros'))

    return "Método não permitido", 405

# ================================
# MEMBROS - NOVO
# ================================
@app.route('/membro/novo', methods=['GET', 'POST'])
@login_required
def novo_membro():
    # Permite níveis 1-4
    if current_user.nivel_acesso > 4:
        flash("Acesso negado.", "danger")
        return redirect(url_for('index'))
    form = MembroForm()

    if form.validate_on_submit():
        filename = 'default.jpg'
        if form.foto.data:
            filename = secure_filename(form.foto.data.filename)
            form.foto.data.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        membro = Membro(
            nome=form.nome.data,
            email=form.email.data or None,
            telefone=form.telefone.data or None,
            celular=form.celular.data,
            cep=form.cep.data or None,
            endereco=form.endereco.data or None,
            bairro=form.bairro.data or None,
            cidade=form.cidade.data or "São Paulo",
            estado=form.estado.data or "SP",
            data_nascimento=form.data_nascimento.data,
            estado_civil=form.estado_civil.data or None,
            conjuge=form.conjuge.data or None,
            filhos=form.filhos.data or 0,
            batizado=form.batizado.data,
            data_batismo=form.data_batismo.data,
            ministerio=form.ministerio.data,
            foto=filename,
            status=form.status.data,
            ativo=(form.status.data == 'ativo')
        )
        db.session.add(membro)
        db.session.commit()
        flash("Membro cadastrado com sucesso!", "success")
        return redirect(url_for('listar_membros'))

    return render_template('secretaria/membros_form.html', form=form, title="Novo Membro")

# ================================
# MEMBROS - EXCLUIR
# ================================
@app.route('/membro/excluir/<int:id>', methods=['POST'])
@secretaria_required
@login_required
def excluir_membro(id):
    membro = Membro.query.get_or_404(id)
    db.session.delete(membro)
    db.session.commit()
    flash(f"Membro {membro.nome} excluído!", "info")
    return redirect(url_for('listar_membros'))

# ================================
# IMPORTAR MEMBROS
# ================================
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
                        cidade=row.get('cidade', '').strip() or 'São Paulo',
                        estado=row.get('estado', '').strip() or 'SP',
                        conjuge=row.get('conjuge', '').strip(),
                        ativo=True,
                        status='ativo'
                    )
                    db.session.add(membro)
                    count += 1
                except Exception as e:
                    flash(f"Erro na linha: {row} → {e}", "danger")
            db.session.commit()
            flash(f"{count} membros importados com sucesso!", "success")
            return redirect(url_for('listar_membros'))

    return render_template('secretaria/importar_membros.html')

# ================================
# FINANCEIRO
# ================================
def gerar_dados_grafico():
    meses_grafico = []
    saldos_grafico = []
    hoje = datetime.now()
    for i in range(11, -1, -1):
        mes = (hoje - timedelta(days=30*i)).strftime('%b')
        inicio_mes = datetime(hoje.year, hoje.month - i, 1) if hoje.month - i > 0 else datetime(hoje.year - 1, 12 + (hoje.month - i), 1)
        fim_mes = inicio_mes + timedelta(days=31) - timedelta(days=1)
        entradas = db.session.query(func.sum(Transacao.valor)).filter(
            Transacao.data.between(inicio_mes, fim_mes),
            Transacao.tipo.in_(['dizimo', 'oferta', 'doacao'])
        ).scalar() or 0
        saidas = db.session.query(func.sum(Transacao.valor)).filter(
            Transacao.data.between(inicio_mes, fim_mes),
            Transacao.tipo == 'despesa'
        ).scalar() or 0
        saldos_grafico.append(entradas - saidas)
        meses_grafico.append(mes)
    return meses_grafico, saldos_grafico

@app.route('/financeiro', methods=['GET', 'POST'])
@login_required  # apenas login_required para permitir visualização restrita
def financeiro():
    form = TransacaoForm()

    membros = Membro.query.order_by(Membro.nome).all()
    form.membro_id.choices = [(0, '-- Nenhum --')] + [(m.id, m.nome) for m in membros]

    mes = request.args.get('mes', datetime.now().strftime('%Y-%m'))
    ano, mes_num = map(int, mes.split('-'))
    inicio_mes = datetime(ano, mes_num, 1)
    proximo_mes = inicio_mes + timedelta(days=32)
    fim_mes = datetime(proximo_mes.year, proximo_mes.month, 1) - timedelta(days=1)

    # Inserção só se permitido (nível <= 3)
    if form.validate_on_submit() and current_user.nivel_acesso <= 3:
        nova = Transacao(
            data=form.data_transacao.data,
            tipo=form.tipo.data,
            categoria=form.categoria.data,
            valor=form.valor.data,
            metodo=form.metodo.data,
            membro_id=form.membro_id.data if form.membro_id.data else None,
            is_fixo=bool(int(form.is_fixo.data))
        )
        db.session.add(nova)
        db.session.commit()
        flash('Transação registrada com sucesso!', 'success')
        return redirect(url_for('financeiro', mes=mes))

    # --- VISUALIZAÇÃO RESTRITA PARA MEMBROS (nível > 3) ---
    is_restrito = current_user.nivel_acesso > 3
    if is_restrito:
        membro = current_user.membro
        if not membro:
            flash("Você ainda não está vinculado a um membro no sistema.", "warning")
            return redirect(url_for('index'))

        transacoes = Transacao.query.filter_by(membro_id=membro.id).filter(
            Transacao.data >= inicio_mes,
            Transacao.data <= fim_mes
        ).order_by(Transacao.data.desc()).all()
        form = None  # Esconde o formulário para membros
    else:
        transacoes = Transacao.query.filter(
            Transacao.data >= inicio_mes,
            Transacao.data <= fim_mes
        ).order_by(Transacao.data.desc()).all()

    # --- CÁLCULOS ---
    total_entradas = sum(t.valor for t in transacoes if t.tipo in ['dizimo', 'oferta', 'doacao'])
    total_saidas = sum(t.valor for t in transacoes if t.tipo == 'despesa')
    total_fixos = sum(t.valor for t in transacoes if t.is_fixo) + sum(c.valor for c in CustoFixo.query.filter_by(ativo=True).all())

    config = Configuracao.query.first()
    if not config:
        config = Configuracao()
        db.session.add(config)
        db.session.commit()

    saldo_final = total_entradas - total_saidas
    provisao = config.provisao_extras or 0.0
    saldo_real = saldo_final - provisao - total_fixos

    media_dizimo = 151
    dizimistas_necessarios = int(round(total_fixos / media_dizimo, 0)) if media_dizimo > 0 else 0

    meses_grafico, saldos_grafico = gerar_dados_grafico()
    mes_atual = datetime.now().strftime('%B/%Y').capitalize()
    saldo_status = "positivo" if saldo_final >= 0 else "negativo"

    return render_template(
        'secretaria/financeiro.html',
        form=form,
        transacoes=transacoes,
        total_entradas=total_entradas,
        total_saidas=total_saidas,
        total_fixos=total_fixos,
        saldo_real=saldo_real,
        provisao_extras=provisao,
        saldo_final=saldo_final,
        dizimistas_necessarios=dizimistas_necessarios,
        mes=mes,
        meses_grafico=meses_grafico,
        saldos_grafico=saldos_grafico,
        mes_atual=mes_atual,
        saldo_status=saldo_status,
        is_membro=is_restrito
    )


@app.route('/financeiro_membro')
@login_required
def financeiro_membro():
    # Só usuários vinculados a um membro podem acessar
    membro = current_user.membro
    if not membro:
        flash("Você ainda não está vinculado a um membro no sistema.", "warning")
        return redirect(url_for('index'))

    # Filtrar mês atual ou selecionado
    mes = request.args.get('mes', datetime.now().strftime('%Y-%m'))
    ano, mes_num = map(int, mes.split('-'))
    inicio_mes = datetime(ano, mes_num, 1)
    proximo_mes = inicio_mes + timedelta(days=32)
    fim_mes = datetime(proximo_mes.year, proximo_mes.month, 1) - timedelta(days=1)

    # Buscar transações do membro
    transacoes = Transacao.query.filter_by(membro_id=membro.id).filter(
        Transacao.data >= inicio_mes,
        Transacao.data <= fim_mes
    ).order_by(Transacao.data.desc()).all()

    total_entradas = sum(t.valor for t in transacoes if t.tipo in ['dizimo', 'oferta', 'doacao'])
    total_saidas = sum(t.valor for t in transacoes if t.tipo == 'despesa')

    saldo_final = total_entradas - total_saidas

    meses_grafico, saldos_grafico = gerar_dados_grafico()  # reutiliza função do financeiro

    return render_template(
        'secretaria/financeiro_membro.html',
        transacoes=transacoes,
        total_entradas=total_entradas,
        total_saidas=total_saidas,
        saldo_final=saldo_final,
        meses_grafico=meses_grafico,
        saldos_grafico=saldos_grafico,
        mes=mes,
        mes_atual=datetime.now().strftime('%B/%Y').capitalize()
    )


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

@app.route('/financeiro/configuracao', methods=['GET', 'POST'])
@financeiro_required
@login_required
def configurar_financeiro():
    config = Configuracao.query.first()
    if not config:
        config = Configuracao()
        db.session.add(config)
        db.session.commit()

    if request.method == 'POST':
        config.provisao_extras = float(request.form['provisao_extras'])
        config.salario_medio = float(request.form['salario_medio'])
        db.session.commit()
        flash("Configuração salva!", "success")
        return redirect(url_for('financeiro'))

    return render_template('secretaria/configuracao_financeiro.html', config=config)

# ================================
# EXPORTAÇÃO
# ================================
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

    caminho_wk = os.getenv('WKHTMLTOPDF_PATH', r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe')
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

# ================================
# EVENTOS
# ================================
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

# ================================
# ROTA STUB PARA /pdv (se precisar)
# ================================
@app.route('/pdv')
@login_required
def pdv():
    return render_template('secretaria/pdv.html')  # Crie o template se quiser

# ================================
# INICIALIZAÇÃO
# ================================
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
                is_secretaria=True,
                is_admin=True
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

# ================================
# GERENCIAMENTO DE USUÁRIOS (versão corrigida)
# ================================
@app.route('/secretaria/usuarios/listar')
@login_required
def usuarios_listar():
    if current_user.nivel_acesso > 3:
        flash("Acesso negado.", "danger")
        return redirect(url_for('index'))

    usuarios = User.query.order_by(User.nome.asc()).all()
    return render_template('secretaria/usuarios_list.html', usuarios=usuarios)


@app.route('/secretaria/usuarios/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def usuarios_editar(id):
    if current_user.nivel_acesso > 3:
        flash("Acesso negado.", "danger")
        return redirect(url_for('index'))

    usuario = User.query.get_or_404(id)
    membros = Membro.query.order_by(Membro.nome.asc()).all()

    if request.method == 'POST':
        usuario.nome = request.form.get('nome')
        usuario.email = request.form.get('email')
        usuario.nivel_acesso = int(request.form.get('nivel_acesso', usuario.nivel_acesso))
        usuario.membro_id = int(request.form.get('membro_id')) if request.form.get('membro_id') else None

        nova_senha = request.form.get('senha')
        if nova_senha:
            usuario.senha = generate_password_hash(nova_senha)

        db.session.commit()
        flash("Usuário atualizado com sucesso!", "success")
        return redirect(url_for('usuarios_listar'))

    return render_template('secretaria/usuarios_edit.html', usuario=usuario, membros=membros)


@app.route('/secretaria/usuarios/excluir/<int:id>', methods=['POST'])
@login_required
def usuarios_excluir(id):
    if current_user.nivel_acesso != 1:
        flash("Apenas o Administrador pode excluir usuários.", "danger")
        return redirect(url_for('usuarios_listar'))

    usuario = User.query.get_or_404(id)
    db.session.delete(usuario)
    db.session.commit()
    flash("Usuário excluído com sucesso!", "info")
    return redirect(url_for('usuarios_listar'))


if __name__ == '__main__':
    with app.app_context():
        create_initial_data()
    app.run(debug=True)