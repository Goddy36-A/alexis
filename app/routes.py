from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from .database import get_db, log_action
from .nlp_engine import analyze
from functools import wraps

main = Blueprint('main', __name__)

# ── DECORATORS ────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated

def expert_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') not in ('expert', 'admin'):
            flash('Expert access required.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated

# ── INDEX / SEARCH ─────────────────────────────────────────────────────────────

@main.route('/')
def index():
    db = get_db()
    q = request.args.get('q', '').strip()
    if q:
        articles = db.execute('''
            SELECT a.*, u.username as submitter
            FROM articles a LEFT JOIN users u ON a.submitted_by=u.id
            WHERE a.title LIKE ? OR a.content LIKE ? OR a.source LIKE ?
            ORDER BY a.created_at DESC LIMIT 40
        ''', (f'%{q}%', f'%{q}%', f'%{q}%')).fetchall()
    else:
        articles = db.execute('''
            SELECT a.*, u.username as submitter
            FROM articles a LEFT JOIN users u ON a.submitted_by=u.id
            ORDER BY a.created_at DESC LIMIT 20
        ''').fetchall()
    stats = db.execute('''
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN final_verdict='fake' THEN 1 ELSE 0 END) as fake,
            SUM(CASE WHEN final_verdict='real' THEN 1 ELSE 0 END) as real,
            SUM(CASE WHEN final_verdict='pending' THEN 1 ELSE 0 END) as pending
        FROM articles
    ''').fetchone()
    return render_template('index.html', articles=articles, stats=stats, q=q)

# ── SUBMIT ─────────────────────────────────────────────────────────────────────

@main.route('/submit', methods=['GET', 'POST'])
@login_required
def submit():
    if request.method == 'POST':
        title   = request.form['title'].strip()
        content = request.form['content'].strip()
        url     = request.form.get('url', '').strip()
        source  = request.form.get('source', '').strip()
        if not title or not content:
            flash('Title and content are required.', 'error')
            return render_template('submit.html')
        result = analyze(title, content, url)
        db = get_db()
        cur = db.execute('''
            INSERT INTO articles (title, content, url, source, submitted_by,
                nlp_score, nlp_label, final_verdict)
            VALUES (?,?,?,?,?,?,?,?)
        ''', (title, content, url, source, session['user_id'],
              result['fake_probability'], result['label'], 'pending'))
        article_id = cur.lastrowid
        log_action(db, session['user_id'], 'submit_article', 'article', article_id, title[:100])
        # Badge: first submission
        if not db.execute('SELECT id FROM badges WHERE user_id=? AND badge_name=?',
                          (session['user_id'], 'First Submission')).fetchone():
            db.execute('INSERT INTO badges (user_id, badge_name) VALUES (?,?)',
                       (session['user_id'], 'First Submission'))
        db.commit()
        flash('Article submitted and analysed!', 'success')
        return redirect(url_for('main.article', article_id=article_id))
    return render_template('submit.html')

# ── ARTICLE DETAIL ─────────────────────────────────────────────────────────────

@main.route('/article/<int:article_id>')
def article(article_id):
    db = get_db()
    art = db.execute('''
        SELECT a.*, u.username as submitter
        FROM articles a LEFT JOIN users u ON a.submitted_by=u.id
        WHERE a.id=?
    ''', (article_id,)).fetchone()
    if not art:
        flash('Article not found.', 'error')
        return redirect(url_for('main.index'))
    votes = db.execute('''
        SELECT v.*, u.username FROM votes v JOIN users u ON v.user_id=u.id
        WHERE v.article_id=?
    ''', (article_id,)).fetchall()
    comments = db.execute('''
        SELECT c.*, u.username FROM comments c JOIN users u ON c.user_id=u.id
        WHERE c.article_id=? ORDER BY c.created_at
    ''', (article_id,)).fetchall()
    expert_reviews = db.execute('''
        SELECT er.*, u.username FROM expert_reviews er
        JOIN users u ON er.reviewer_id=u.id WHERE er.article_id=?
    ''', (article_id,)).fetchall()
    user_vote = None
    if 'user_id' in session:
        user_vote = db.execute('SELECT * FROM votes WHERE article_id=? AND user_id=?',
                               (article_id, session['user_id'])).fetchone()
    vote_summary = _vote_summary(votes)
    return render_template('article.html', art=art, votes=votes, comments=comments,
                           expert_reviews=expert_reviews,
                           user_vote=user_vote, vote_summary=vote_summary)

# ── EDIT ARTICLE ───────────────────────────────────────────────────────────────

@main.route('/article/<int:article_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_article(article_id):
    db = get_db()
    art = db.execute('SELECT * FROM articles WHERE id=?', (article_id,)).fetchone()
    if not art:
        flash('Article not found.', 'error')
        return redirect(url_for('main.index'))
    # Only owner or admin can edit
    if art['submitted_by'] != session['user_id'] and session.get('role') != 'admin':
        flash('You can only edit your own submissions.', 'error')
        return redirect(url_for('main.article', article_id=article_id))
    if request.method == 'POST':
        title   = request.form['title'].strip()
        content = request.form['content'].strip()
        url     = request.form.get('url', '').strip()
        source  = request.form.get('source', '').strip()
        if not title or not content:
            flash('Title and content are required.', 'error')
            return render_template('edit_article.html', art=art)
        # Re-run NLP on updated content
        result = analyze(title, content, url)
        db.execute('''
            UPDATE articles SET title=?, content=?, url=?, source=?,
                nlp_score=?, nlp_label=?, final_verdict='pending'
            WHERE id=?
        ''', (title, content, url, source,
              result['fake_probability'], result['label'], article_id))
        log_action(db, session['user_id'], 'edit_article', 'article', article_id, title[:100])
        db.commit()
        flash('Article updated and re-analysed.', 'success')
        return redirect(url_for('main.article', article_id=article_id))
    return render_template('edit_article.html', art=art)

# ── DELETE ARTICLE ─────────────────────────────────────────────────────────────

@main.route('/article/<int:article_id>/delete', methods=['POST'])
@login_required
def delete_article(article_id):
    db = get_db()
    art = db.execute('SELECT * FROM articles WHERE id=?', (article_id,)).fetchone()
    if not art:
        flash('Article not found.', 'error')
        return redirect(url_for('main.index'))
    if art['submitted_by'] != session['user_id'] and session.get('role') != 'admin':
        flash('You can only delete your own submissions.', 'error')
        return redirect(url_for('main.article', article_id=article_id))
    # Cascade delete related records
    db.execute('DELETE FROM votes WHERE article_id=?', (article_id,))
    db.execute('DELETE FROM comments WHERE article_id=?', (article_id,))
    db.execute('DELETE FROM expert_reviews WHERE article_id=?', (article_id,))
    db.execute('DELETE FROM articles WHERE id=?', (article_id,))
    log_action(db, session['user_id'], 'delete_article', 'article', article_id, art['title'][:100])
    db.commit()
    flash('Article deleted.', 'success')
    return redirect(url_for('main.index'))

# ── VOTE ───────────────────────────────────────────────────────────────────────

@main.route('/vote/<int:article_id>', methods=['POST'])
@login_required
def vote(article_id):
    vote_val   = request.form.get('vote', '').strip()
    confidence = int(request.form.get('confidence', 3))
    reason     = request.form.get('reason', '').strip()
    if vote_val not in ('fake', 'real', 'unsure'):
        flash('Please select a vote option.', 'error')
        return redirect(url_for('main.article', article_id=article_id))
    db = get_db()
    existing = db.execute('SELECT id FROM votes WHERE article_id=? AND user_id=?',
                          (article_id, session['user_id'])).fetchone()
    if existing:
        db.execute('UPDATE votes SET vote=?, confidence=?, reason=? WHERE id=?',
                   (vote_val, confidence, reason, existing['id']))
        log_action(db, session['user_id'], 'update_vote', 'article', article_id, vote_val)
    else:
        db.execute('INSERT INTO votes (article_id, user_id, vote, confidence, reason) VALUES (?,?,?,?,?)',
                   (article_id, session['user_id'], vote_val, confidence, reason))
        log_action(db, session['user_id'], 'cast_vote', 'article', article_id, vote_val)
    votes = db.execute('SELECT vote, confidence FROM votes WHERE article_id=?',
                       (article_id,)).fetchall()
    _update_verdict(db, article_id, votes)
    db.commit()
    _check_voter_badges(db, session['user_id'])
    flash('Vote recorded!', 'success')
    return redirect(url_for('main.article', article_id=article_id))

def _vote_summary(votes):
    total = len(votes)
    if not total:
        return {'total': 0, 'fake_pct': 0, 'real_pct': 0, 'unsure_pct': 0,
                'fake': 0, 'real': 0, 'unsure': 0}
    fake   = sum(1 for v in votes if v['vote'] == 'fake')
    real   = sum(1 for v in votes if v['vote'] == 'real')
    unsure = total - fake - real
    return {
        'total': total,
        'fake_pct':   round(fake / total * 100),
        'real_pct':   round(real / total * 100),
        'unsure_pct': round(unsure / total * 100),
        'fake': fake, 'real': real, 'unsure': unsure,
    }

def _update_verdict(db, article_id, votes):
    if not votes:
        return
    weighted_fake = sum(v['confidence'] for v in votes if v['vote'] == 'fake')
    total_w = sum(v['confidence'] for v in votes) or 1
    community_score = weighted_fake / total_w
    if community_score >= 0.6 and len(votes) >= 3:
        verdict = 'fake'
    elif community_score <= 0.35 and len(votes) >= 3:
        verdict = 'real'
    else:
        verdict = 'pending'
    db.execute('UPDATE articles SET community_score=?, vote_count=?, final_verdict=? WHERE id=?',
               (community_score, len(votes), verdict, article_id))

def _check_voter_badges(db, user_id):
    count = db.execute('SELECT COUNT(*) as c FROM votes WHERE user_id=?', (user_id,)).fetchone()['c']
    for milestone, badge in {1: 'First Vote', 10: 'Active Voter', 50: 'Truth Guardian', 100: 'Community Pillar'}.items():
        if count >= milestone:
            if not db.execute('SELECT id FROM badges WHERE user_id=? AND badge_name=?',
                              (user_id, badge)).fetchone():
                db.execute('INSERT INTO badges (user_id, badge_name) VALUES (?,?)', (user_id, badge))
    db.commit()

# ── COMMENT ────────────────────────────────────────────────────────────────────

@main.route('/comment/<int:article_id>', methods=['POST'])
@login_required
def comment(article_id):
    content = request.form['content'].strip()
    if not content:
        flash('Comment cannot be empty.', 'error')
    else:
        db = get_db()
        db.execute('INSERT INTO comments (article_id, user_id, content) VALUES (?,?,?)',
                   (article_id, session['user_id'], content))
        log_action(db, session['user_id'], 'post_comment', 'article', article_id)
        db.commit()
        flash('Comment posted.', 'success')
    return redirect(url_for('main.article', article_id=article_id))

# ── EXPERT REVIEW ──────────────────────────────────────────────────────────────

@main.route('/expert_review/<int:article_id>', methods=['POST'])
@login_required
@expert_required
def expert_review(article_id):
    verdict     = request.form['verdict']
    explanation = request.form['explanation'].strip()
    evidence    = request.form.get('evidence', '').strip()
    if verdict not in ('fake', 'real', 'misleading'):
        flash('Invalid verdict.', 'error')
        return redirect(url_for('main.article', article_id=article_id))
    db = get_db()
    db.execute('''
        INSERT INTO expert_reviews (article_id, reviewer_id, verdict, explanation, evidence_links)
        VALUES (?,?,?,?,?)
    ''', (article_id, session['user_id'], verdict, explanation, evidence))
    db.execute('UPDATE articles SET final_verdict=? WHERE id=?', (verdict, article_id))
    log_action(db, session['user_id'], 'expert_review', 'article', article_id, verdict)
    db.commit()
    flash('Expert review published.', 'success')
    return redirect(url_for('main.article', article_id=article_id))

# ── LEADERBOARD ────────────────────────────────────────────────────────────────

@main.route('/leaderboard')
def leaderboard():
    db = get_db()
    users = db.execute('''
        SELECT u.id, u.username, u.reputation,
            (SELECT COUNT(*) FROM votes WHERE user_id=u.id) as vote_count,
            (SELECT COUNT(*) FROM articles WHERE submitted_by=u.id) as article_count,
            (SELECT GROUP_CONCAT(badge_name, ', ') FROM badges WHERE user_id=u.id) as badges
        FROM users u ORDER BY vote_count DESC LIMIT 20
    ''').fetchall()
    return render_template('leaderboard.html', users=users)

# ── DASHBOARD ──────────────────────────────────────────────────────────────────

@main.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    user_id = session['user_id']
    my_articles = db.execute(
        'SELECT * FROM articles WHERE submitted_by=? ORDER BY created_at DESC', (user_id,)
    ).fetchall()
    my_votes = db.execute('''
        SELECT v.*, a.title FROM votes v JOIN articles a ON v.article_id=a.id
        WHERE v.user_id=? ORDER BY v.created_at DESC
    ''', (user_id,)).fetchall()
    my_badges = db.execute(
        'SELECT * FROM badges WHERE user_id=? ORDER BY awarded_at DESC', (user_id,)
    ).fetchall()
    return render_template('dashboard.html',
                           my_articles=my_articles, my_votes=my_votes, my_badges=my_badges)

# ── ADMIN PANEL ────────────────────────────────────────────────────────────────

@main.route('/admin')
@login_required
@admin_required
def admin_panel():
    db = get_db()
    users = db.execute('''
        SELECT u.*,
            (SELECT COUNT(*) FROM votes WHERE user_id=u.id) as vote_count,
            (SELECT COUNT(*) FROM articles WHERE submitted_by=u.id) as article_count
        FROM users u ORDER BY u.created_at DESC
    ''').fetchall()
    articles = db.execute('''
        SELECT a.*, u.username as submitter
        FROM articles a LEFT JOIN users u ON a.submitted_by=u.id
        ORDER BY a.created_at DESC LIMIT 30
    ''').fetchall()
    audit = db.execute('''
        SELECT al.*, u.username FROM audit_log al
        LEFT JOIN users u ON al.user_id=u.id
        ORDER BY al.created_at DESC LIMIT 50
    ''').fetchall()
    stats = db.execute('''
        SELECT
            (SELECT COUNT(*) FROM users) as total_users,
            (SELECT COUNT(*) FROM articles) as total_articles,
            (SELECT COUNT(*) FROM votes) as total_votes,
            (SELECT COUNT(*) FROM comments) as total_comments
    ''').fetchone()
    return render_template('admin.html', users=users, articles=articles,
                           audit=audit, stats=stats)

@main.route('/admin/set_role', methods=['POST'])
@login_required
@admin_required
def admin_set_role():
    user_id = int(request.form['user_id'])
    new_role = request.form['role']
    if new_role not in ('user', 'expert', 'admin'):
        flash('Invalid role.', 'error')
        return redirect(url_for('main.admin_panel'))
    db = get_db()
    target = db.execute('SELECT username FROM users WHERE id=?', (user_id,)).fetchone()
    db.execute('UPDATE users SET role=? WHERE id=?', (new_role, user_id))
    log_action(db, session['user_id'], 'set_role', 'user', user_id,
               f"{target['username']} → {new_role}")
    db.commit()
    flash(f"Role updated to {new_role}.", 'success')
    return redirect(url_for('main.admin_panel'))

@main.route('/admin/delete_user', methods=['POST'])
@login_required
@admin_required
def admin_delete_user():
    user_id = int(request.form['user_id'])
    if user_id == session['user_id']:
        flash('You cannot delete your own account.', 'error')
        return redirect(url_for('main.admin_panel'))
    db = get_db()
    target = db.execute('SELECT username FROM users WHERE id=?', (user_id,)).fetchone()
    if target:
        db.execute('DELETE FROM votes WHERE user_id=?', (user_id,))
        db.execute('DELETE FROM comments WHERE user_id=?', (user_id,))
        db.execute('DELETE FROM badges WHERE user_id=?', (user_id,))
        db.execute('DELETE FROM users WHERE id=?', (user_id,))
        log_action(db, session['user_id'], 'delete_user', 'user', user_id, target['username'])
        db.commit()
        flash(f"User '{target['username']}' removed.", 'success')
    return redirect(url_for('main.admin_panel'))

@main.route('/admin/delete_article', methods=['POST'])
@login_required
@admin_required
def admin_delete_article():
    article_id = int(request.form['article_id'])
    db = get_db()
    art = db.execute('SELECT title FROM articles WHERE id=?', (article_id,)).fetchone()
    if art:
        db.execute('DELETE FROM votes WHERE article_id=?', (article_id,))
        db.execute('DELETE FROM comments WHERE article_id=?', (article_id,))
        db.execute('DELETE FROM expert_reviews WHERE article_id=?', (article_id,))
        db.execute('DELETE FROM articles WHERE id=?', (article_id,))
        log_action(db, session['user_id'], 'admin_delete_article', 'article',
                   article_id, art['title'][:100])
        db.commit()
        flash('Article removed.', 'success')
    return redirect(url_for('main.admin_panel'))

# ── AUDIT LOG (standalone page) ────────────────────────────────────────────────

@main.route('/admin/audit')
@login_required
@admin_required
def audit_log():
    db = get_db()
    logs = db.execute('''
        SELECT al.*, u.username FROM audit_log al
        LEFT JOIN users u ON al.user_id=u.id
        ORDER BY al.created_at DESC LIMIT 200
    ''').fetchall()
    return render_template('audit_log.html', logs=logs)
