from flask import Blueprint, jsonify, request, session
from .database import get_db
from .nlp_engine import analyze

api = Blueprint('api', __name__)

@api.route('/analyze', methods=['POST'])
def api_analyze():
    data    = request.get_json(force=True)
    title   = data.get('title', '')
    content = data.get('content', '')
    url     = data.get('url', '')
    if not title or not content:
        return jsonify({'error': 'title and content required'}), 400
    result = analyze(title, content, url)
    return jsonify(result)

@api.route('/articles')
def api_articles():
    db = get_db()
    page  = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    offset = (page - 1) * limit
    rows = db.execute(
        'SELECT id, title, nlp_label, final_verdict, vote_count, created_at FROM articles ORDER BY created_at DESC LIMIT ? OFFSET ?',
        (limit, offset)
    ).fetchall()
    return jsonify([dict(r) for r in rows])

@api.route('/article/<int:article_id>/stats')
def article_stats(article_id):
    db = get_db()
    art   = db.execute('SELECT * FROM articles WHERE id=?', (article_id,)).fetchone()
    if not art:
        return jsonify({'error': 'not found'}), 404
    votes = db.execute('SELECT vote, confidence FROM votes WHERE article_id=?', (article_id,)).fetchall()
    total = len(votes)
    return jsonify({
        'article_id': article_id,
        'nlp_score': art['nlp_score'],
        'nlp_label': art['nlp_label'],
        'community_score': art['community_score'],
        'final_verdict': art['final_verdict'],
        'vote_count': total,
        'breakdown': {
            'fake':  sum(1 for v in votes if v['vote'] == 'fake'),
            'real':  sum(1 for v in votes if v['vote'] == 'real'),
            'unsure': sum(1 for v in votes if v['vote'] == 'unsure'),
        }
    })

@api.route('/leaderboard')
def api_leaderboard():
    db = get_db()
    rows = db.execute('''
        SELECT u.username,
            (SELECT COUNT(*) FROM votes WHERE user_id=u.id) as votes
        FROM users u ORDER BY votes DESC LIMIT 10
    ''').fetchall()
    return jsonify([dict(r) for r in rows])
