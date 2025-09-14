from flask import Flask

app = Flask(__name__)

@app.route('/')
def test():
    return '<h1>Flask is working!</h1><p>Water monitoring system is accessible.</p>'

if __name__ == '__main__':
    print("Starting test server on http://127.0.0.1:5000")
    app.run(debug=True, host='127.0.0.1', port=5000)