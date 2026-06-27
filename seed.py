"""
seed.py — Populate CFND with demo users, articles and votes for testing.
Run once: python seed.py
"""
import sqlite3
from werkzeug.security import generate_password_hash
from app.nlp_engine import analyze

DB = 'cfnd.db'

DEMO_USERS = [
    ('admin',      'admin@cfnd.ug',   'admin123',   'admin'),
    ('expert1',    'expert@cfnd.ug',  'expert123',  'expert'),
    ('alice',      'alice@cfnd.ug',   'alice123',   'user'),
    ('bob',        'bob@cfnd.ug',     'bob123',     'user'),
    ('community',  'comm@cfnd.ug',    'comm123',    'user'),
]

DEMO_ARTICLES = [
    {
        'title': 'Government secretly adds 5G chips to COVID vaccines, experts reveal',
        'content': (
            'BREAKING: Sources close to the government have EXPOSED a shocking conspiracy! '
            'Scientists and experts are BAFFLED after discovering that COVID vaccines '
            'contain hidden 5G microchips. Share this before they delete it! '
            'The mainstream media WON\'T report this. Wake up, people! '
            'This CONFIRMED bombshell changes EVERYTHING we know about the vaccination programme.'
        ),
        'url': 'https://beforeitsnews.example.com/5g-chips',
        'source': 'BeforeItsNews',
    },
    {
        'title': 'WHO releases updated malaria prevention guidelines for Sub-Saharan Africa',
        'content': (
            'The World Health Organization on Tuesday released updated guidelines for malaria '
            'prevention across Sub-Saharan Africa, recommending expanded use of the RTS,S vaccine '
            'alongside existing insecticide-treated nets. According to the report, countries including '
            'Uganda, Kenya, and Ghana are expected to incorporate the new recommendations into their '
            'national health programmes by the end of 2025. The guidelines are based on clinical trial '
            'data from over 15,000 participants across seven countries, peer-reviewed and published '
            'in The Lancet. "These changes represent the strongest evidence base we have ever had for '
            'malaria prevention," said Dr Amina Otieno, WHO regional director.'
        ),
        'url': 'https://who.int/malaria-guidelines-2025',
        'source': 'WHO',
    },
    {
        'title': 'Local Ugandan entrepreneur launches AI-powered crop disease detection app',
        'content': (
            'A Mbarara-based software developer has launched a mobile application that uses '
            'artificial intelligence to detect crop diseases from smartphone photographs. '
            'The app, called FarmEye, has been piloted in Kiruhura and Isingiro districts '
            'with support from the Uganda Communications Commission. According to the developer, '
            'early trials showed 87% accuracy in identifying cassava mosaic disease, banana '
            'bacterial wilt, and maize streak virus. The app is available free on Android devices '
            'and requires no internet connection for core features.'
        ),
        'url': 'https://monitor.co.ug/tech/farmeye-app',
        'source': 'Daily Monitor',
    },
]

def seed():
    from app import create_app
    app = create_app()
    with app.app_context():
        db = sqlite3.connect(DB)
        db.row_factory = sqlite3.Row

        # Users
        user_ids = {}
        for uname, email, pw, role in DEMO_USERS:
            existing = db.execute('SELECT id FROM users WHERE username=?', (uname,)).fetchone()
            if existing:
                user_ids[uname] = existing['id']
                continue
            cur = db.execute(
                'INSERT INTO users (username, email, password_hash, role) VALUES (?,?,?,?)',
                (uname, email, generate_password_hash(pw), role)
            )
            db.commit()
            user_ids[uname] = cur.lastrowid
            print(f'  Created user: {uname} ({role})')

        # Articles
        article_ids = []
        for art in DEMO_ARTICLES:
            existing = db.execute('SELECT id FROM articles WHERE title=?', (art['title'],)).fetchone()
            if existing:
                article_ids.append(existing['id'])
                continue
            result = analyze(art['title'], art['content'], art.get('url', ''))
            cur = db.execute('''
                INSERT INTO articles (title, content, url, source, submitted_by, nlp_score, nlp_label, final_verdict)
                VALUES (?,?,?,?,?,?,?,?)
            ''', (
                art['title'], art['content'], art.get('url',''), art.get('source',''),
                user_ids['alice'], result['fake_probability'], result['label'], 'pending'
            ))
            db.commit()
            article_ids.append(cur.lastrowid)
            print(f'  Created article: {art["title"][:50]}... | NLP={result["label"]}')

        # Votes
        sample_votes = [
            (article_ids[0], user_ids['alice'],     'fake',  5, 'Clearly fake — no credible sources'),
            (article_ids[0], user_ids['bob'],       'fake',  4, '5G in vaccines is debunked'),
            (article_ids[0], user_ids['community'], 'fake',  5, 'Checked multiple sources'),
            (article_ids[1], user_ids['alice'],     'real',  5, 'WHO is a credible source'),
            (article_ids[1], user_ids['bob'],       'real',  4, 'Cross-referenced with Lancet'),
            (article_ids[2], user_ids['alice'],     'real',  4, 'Local story, verifiable'),
            (article_ids[2], user_ids['bob'],       'unsure',3, 'Accuracy claims need peer review'),
        ]
        for a_id, u_id, vote, conf, reason in sample_votes:
            exists = db.execute('SELECT id FROM votes WHERE article_id=? AND user_id=?', (a_id, u_id)).fetchone()
            if not exists:
                db.execute(
                    'INSERT INTO votes (article_id, user_id, vote, confidence, reason) VALUES (?,?,?,?,?)',
                    (a_id, u_id, vote, conf, reason)
                )
        db.commit()
        print('  Votes seeded.')

        # Expert review
        if article_ids:
            exists = db.execute('SELECT id FROM expert_reviews WHERE article_id=?', (article_ids[0],)).fetchone()
            if not exists:
                db.execute('''
                    INSERT INTO expert_reviews (article_id, reviewer_id, verdict, explanation, evidence_links)
                    VALUES (?,?,?,?,?)
                ''', (
                    article_ids[0], user_ids['expert1'], 'fake',
                    'Claim is entirely fabricated. No peer-reviewed study supports 5G chip insertion via vaccines. '
                    'The source is a known disinformation outlet.',
                    'https://reuters.com/fact-check/5g-chips, https://who.int/covid-19/vaccines/faq'
                ))
                db.execute('UPDATE articles SET final_verdict=? WHERE id=?', ('fake', article_ids[0]))
                db.commit()
                print('  Expert review seeded.')

        # Badges
        db.execute("INSERT OR IGNORE INTO badges (user_id, badge_name) VALUES (?,?)", (user_ids['alice'], 'First Submission'))
        db.execute("INSERT OR IGNORE INTO badges (user_id, badge_name) VALUES (?,?)", (user_ids['alice'], 'First Vote'))
        db.execute("INSERT OR IGNORE INTO badges (user_id, badge_name) VALUES (?,?)", (user_ids['expert1'], 'First Vote'))
        db.commit()

        db.close()
        print('\n✅  Seed complete.')
        print('\nDemo accounts:')
        for uname, _, pw, role in DEMO_USERS:
            print(f'  {uname:12} / {pw:12}  [{role}]')

if __name__ == '__main__':
    seed()
