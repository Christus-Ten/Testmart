import os
import random
import string
from flask import Flask, request, jsonify, render_template, abort
from models import db, Command

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Clé API simple pour l'upload (à changer en production)
UPLOAD_API_KEY = os.environ.get("UPLOAD_API_KEY", "secret-key-change-me")

def generate_short_id(length=6):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

@app.route('/')
def index():
    commands = Command.query.order_by(Command.views.desc()).limit(10).all()
    return render_template('index.html', commands=commands)

# --- API Endpoints ---

@app.route('/api/items', methods=['GET'])
def list_items():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    search = request.args.get('search', '')

    query = Command.query
    if search:
        query = query.filter(Command.name.contains(search) | Command.description.contains(search))

    total = query.count()
    items = query.order_by(Command.created_at.desc()).paginate(page=page, per_page=limit, error_out=False)
    return jsonify({
        "items": [cmd.to_dict() for cmd in items.items],
        "total": total,
        "page": page,
        "totalPages": (total + limit - 1) // limit
    })

@app.route('/api/item/<int:item_id>', methods=['GET'])
def get_item(item_id):
    cmd = Command.query.get_or_404(item_id)
    cmd.views += 1
    db.session.commit()
    return jsonify(cmd.to_dict())

@app.route('/api/lookup/<identifier>', methods=['GET'])
def lookup_item(identifier):
    # identifier peut être un ID numérique ou un short_id
    cmd = None
    if identifier.isdigit():
        cmd = Command.query.get(int(identifier))
    else:
        cmd = Command.query.filter_by(short_id=identifier).first()
    if not cmd:
        abort(404, description="Command not found")
    cmd.views += 1
    db.session.commit()
    return jsonify(cmd.to_dict())

@app.route('/api/trending', methods=['GET'])
def trending():
    # On prend les commandes avec le plus de vues/likes (simple)
    cmds = Command.query.order_by(Command.views.desc()).limit(10).all()
    return jsonify([cmd.to_dict() for cmd in cmds])

@app.route('/raw/<identifier>', methods=['GET'])
def raw_code(identifier):
    cmd = None
    if identifier.isdigit():
        cmd = Command.query.get(int(identifier))
    else:
        cmd = Command.query.filter_by(short_id=identifier).first()
    if not cmd:
        abort(404, description="Command not found")
    return cmd.code, 200, {'Content-Type': 'text/plain; charset=utf-8'}

@app.route('/api/maintenance', methods=['GET'])
def maintenance_status():
    # Pour cet exemple, on considère que le service est toujours actif.
    return jsonify({"enabled": False, "title": "", "message": ""})

@app.route('/api/stats', methods=['GET'])
def stats():
    total_commands = Command.query.count()
    total_likes = db.session.query(db.func.sum(Command.likes)).scalar() or 0
    total_views = db.session.query(db.func.sum(Command.views)).scalar() or 0
    top_authors = db.session.query(Command.author, db.func.count(Command.id)).group_by(Command.author).order_by(db.func.count(Command.id).desc()).first()
    most_viewed = Command.query.order_by(Command.views.desc()).first()
    return jsonify({
        "totalCommands": total_commands,
        "totalLikes": total_likes,
        "totalViews": total_views,
        "dailyActiveUsers": 42,  # simulé
        "totalUploads": total_commands,
        "totalRequests": 1337,
        "topAuthors": [{"_id": top_authors[0], "count": top_authors[1]}] if top_authors else [],
        "topViewed": most_viewed.to_dict() if most_viewed else None
    })

@app.route('/api/items/<int:item_id>/like', methods=['POST'])
def like_item(item_id):
    cmd = Command.query.get_or_404(item_id)
    cmd.likes += 1
    db.session.commit()
    return jsonify({"likes": cmd.likes})

@app.route('/api/items', methods=['POST'])
def upload_item():
    # Vérification simple par clé API (à améliorer)
    api_key = request.headers.get('X-API-Key')
    if api_key != UPLOAD_API_KEY:
        abort(403, description="Invalid API key")

    data = request.get_json()
    if not data or not data.get('itemName') or not data.get('code') or not data.get('authorName'):
        abort(400, description="Missing required fields")

    # Vérifier si un nom similaire existe déjà (optionnel)
    existing = Command.query.filter_by(name=data['itemName']).first()
    if existing:
        abort(409, description="A command with this name already exists")

    cmd = Command(
        short_id=generate_short_id(),
        name=data['itemName'],
        description=data.get('description', ''),
        author=data['authorName'],
        code=data['code'],
        type=data.get('type', 'GoatBot'),
        tags=','.join(data.get('tags', [])),
        difficulty=data.get('difficulty', 'Intermediate')
    )
    db.session.add(cmd)
    db.session.commit()

    return jsonify({
        "success": True,
        "itemId": cmd.id,
        "shortId": cmd.short_id,
        "message": "Upload successful"
    }), 201

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Ajouter des données de démo si la base est vide
        if Command.query.count() == 0:
            demo = Command(
                short_id=generate_short_id(),
                name="demo-command",
                description="A simple demo command",
                author="Aryan Chauhan",
                code='module.exports = { config: { name: "demo" }, onStart: () => {} }',
                views=100,
                likes=10
            )
            db.session.add(demo)
            db.session.commit()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
