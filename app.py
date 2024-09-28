#!/usr/bin/env python3
import requests
import getpass
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session,jsonify
from datetime import datetime

app = Flask(__name__)


app.secret_key = '123'




conexao = sqlite3.connect('messages', check_same_thread=False)
cursor = conexao.cursor()


api_url = "http://learnops.duckdns.org:7111/v3"

cursor.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY,
        timestamp TEXT NOT NULL,
        user_id INT NOT NULL,
        user_name TEXT NOT NULL,
        text TEXT NOT NULL
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS token (
        user_id INTEGER PRIMARY KEY,
        token TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES messages(user_id) ON DELETE CASCADE
    )
''')
     
cursor.execute('''
    CREATE TABLE IF NOT EXISTS ultimo_auth (
        id INTEGER 
    )
''')

def salvarUltimoIdAuth(id):
    cursor.execute('DELETE FROM ultimo_auth')
    
    cursor.execute('''
        INSERT INTO ultimo_auth (id)
        VALUES (?)
    ''', (id,))
    
    conexao.commit()

def obterUltimoIdAuth():
     cursor.execute('SELECT id FROM ultimo_auth LIMIT 1')
     resultado = cursor.fetchone()
     if resultado:
          return resultado[0]
     else:
          return None

def atualizarToken(id, novoToken):
    cursor.execute('''
        INSERT INTO token (user_id, token)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET token=excluded.token
    ''', (id, novoToken))
    conexao.commit()

def pegarToken(id):
    cursor.execute('SELECT token FROM token WHERE user_id = ?', (id,))
    resultado = cursor.fetchone()
    if resultado:
        return resultado[0]
    else:
        print("Nenhum token encontrado para esse usuário.")
        return None

def cadastroUser(nome, password, password2):
    url = f"{api_url}/user"
    if password == password2:
        dados = {
            "name": str(nome),
            "password": str(password)
        }
        response = requests.post(url, json=dados)
        status = response.json()
        return status
    else:
        return {"success": False, "message": "Senhas diferentes, tente novamente!"}

def pegarDadosUser():
     id = input ("Informe o id do Usuario que deseja ver os dados: ")
     url = f"{api_url}/user/{id}"     
     token = pegarToken(obterUltimoIdAuth())
     headers = {
         'Authorization' : token
     }
     response = requests.get(url, headers=headers)
     
     if response.status_code == 200:
          print(response.json())
     else:
          print("erro!")

def autorizarNovoUser():
     id = input("Informe o id do Usuario: ")
     url = f"{api_url}/user/{id}"
     token = pegarToken(obterUltimoIdAuth())
     ativo = input("Digite 1 para ativar\nDigite 0 para desativar: ")
     headers = {
         'Authorization' : token
     }

     if ativo == "1":
           ativo = True
     elif ativo == "0":
           ativo = False
     else:
           print("Entrada inválida. Digite 1 ou 0.")
           ativo = None

     dados = {
         'enable' : ativo
     }
     response = requests.put(url, json=dados, headers=headers)
     print(response.json())

def autenticarUser(id , senha):
    url = f"{api_url}/auth/{id}"

    dados={
          "password" : senha
    }

    response = requests.post(url, json=dados)
     
    if response.status_code == 200:
        resultado = response.json()
        novoToken = resultado.get('token')
        atualizarToken(id, novoToken)
        salvarUltimoIdAuth(id)
        
        return True
    else:
        return False

def mandarMensagem(text):
    url = f"{api_url}/message"
    token = pegarToken(obterUltimoIdAuth())
    headers = {
         'Authorization' : token
    }
    message = {
         'text' : text
    }
    response = requests.post(url, json=message, headers=headers)

def atualizandoBD():
    cursor.execute("SELECT MAX(id) FROM messages")
    ultimoId = cursor.fetchone()

    if ultimoId[0] is not None:
        last = ultimoId[0]
    else:
        last = 0


    token = pegarToken(obterUltimoIdAuth())
    headers ={
         'Authorization' : token
    }

    url = f"{api_url}/message/?last={last}"
    response = requests.get(url, headers=headers ).json()

    listaMensagens = response['data']
    indice = 0
    tamanhoLista = len(listaMensagens)

    while indice < tamanhoLista:
        mensagem = listaMensagens[indice]

        idMensagem = mensagem['id']
        timestamp = mensagem['timestamp']
        userId = mensagem['user_id']
        remetente = mensagem['user_name']
        texto = mensagem['text']

        indice += 1

        comando_insercao = '''
        INSERT OR IGNORE INTO messages (id, timestamp,user_id, user_name, text)
        VALUES (?, ? , ? , ?, ?)
        '''

        valores = (idMensagem, timestamp,userId, remetente, texto)

        cursor.execute(comando_insercao, valores)
        conexao.commit()

def formatarMensagem(id, timestamp, user_id, user_name, text):
    dataHoraObj = datetime.fromisoformat(timestamp)
    dataFormatada = dataHoraObj.strftime("%d/%m/%y")
    horaFormatada = dataHoraObj.strftime("%H:%M")
    
    mensagemFormatada = (
        f"ID: {id}\n"
        f"Nome: {user_name}\n"
        f"ID Usuario: {user_id}\n"
        f"Mensagem: {text}\n"
        f"Data: {dataFormatada}\n"
        f"Hora: {horaFormatada}"
    )
    
    return mensagemFormatada

def mostrarMensagens():
    cursor.execute("SELECT id, timestamp, user_id, user_name, text FROM messages")
    resultados = cursor.fetchall()
    
    listaMensagens = []
    
    for row in resultados:
        id, timestamp, user_id, user_name, text = row
        mensagemFormatada = formatarMensagem(id, timestamp, user_id, user_name, text)
        listaMensagens.append(mensagemFormatada)

    
    return listaMensagens

@app.route('/', methods=['GET', 'POST'])
def index():
    resultado = None

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'login':
            id = request.form['id']
            password = request.form['password']
            user = autenticarUser(id, password)
            if user:
                session['logged_in'] = True
                session['id'] = id
            else:
                resultado = "erro na autenticação"
        elif action == 'cadastro':
            nome = request.form['nome']
            password = request.form['password']
            password2 = request.form['password2']
            resultado = cadastroUser(nome, password, password2)
            return resultado      
        
        elif action == 'send_message' and session.get('logged_in'):
            message = request.form.get('message')
            if message:
                mandarMensagem(message)

    if session.get('logged_in'):
        atualizandoBD()
        mensagens = mostrarMensagens()
    else:
        mensagens = []

    return render_template('index.html', mensagens=mensagens, resultado=resultado)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('id', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)