from flask import Flask, render_template, redirect

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/app')
def redirect_to_port_3000():
    return redirect("http://0.0.0.0:3000", code=302)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=4000, debug=False, use_reloader=False)