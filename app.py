from flask import Flask, render_template, request, redirect, url_for, send_file, make_response, session
# from flask_pwa import PWA
import io
import secrets
import string
from datetime import datetime, timedelta
import math

app = Flask(__name__)
# PWA(app)

# Password strength rules (can be updated as regulations change)
MIN_LENGTH = 12
REQUIRE_UPPER = True
REQUIRE_LOWER = True
REQUIRE_DIGIT = True
REQUIRE_SPECIAL = True
SPECIAL_CHARS = string.punctuation


def generate_password(length=16, use_upper=True, use_lower=True, use_digits=True, use_special=True):
    chars = ''
    if use_upper:
        chars += string.ascii_uppercase
    if use_lower:
        chars += string.ascii_lowercase
    if use_digits:
        chars += string.digits
    if use_special:
        chars += SPECIAL_CHARS
    if not chars:
        chars = string.ascii_letters
    return ''.join(secrets.choice(chars) for _ in range(length))


def analyze_password(password):
    issues = []
    if len(password) < MIN_LENGTH:
        issues.append(f"Password should be at least {MIN_LENGTH} characters long.")
    if REQUIRE_UPPER and not any(c.isupper() for c in password):
        issues.append("Password should include at least one uppercase letter.")
    if REQUIRE_LOWER and not any(c.islower() for c in password):
        issues.append("Password should include at least one lowercase letter.")
    if REQUIRE_DIGIT and not any(c.isdigit() for c in password):
        issues.append("Password should include at least one digit.")
    if REQUIRE_SPECIAL and not any(c in SPECIAL_CHARS for c in password):
        issues.append("Password should include at least one special character.")
    return issues


def suggest_enhancements(password):
    suggestions = []
    if not any(c.isupper() for c in password):
        suggestions.append("Add uppercase letters (A-Z)")
    if not any(c.islower() for c in password):
        suggestions.append("Add lowercase letters (a-z)")
    if not any(c.isdigit() for c in password):
        suggestions.append("Add digits (0-9)")
    if not any(c in SPECIAL_CHARS for c in password):
        suggestions.append("Add special characters (e.g., !@#$%)")
    if len(password) < MIN_LENGTH:
        suggestions.append(f"Increase length to at least {MIN_LENGTH} characters")
    return suggestions


def generate_variations(password, count=3):
    variations = set()
    chars = string.ascii_letters + string.digits + SPECIAL_CHARS
    while len(variations) < count:
        # Insert a random char at a random position
        pos = secrets.randbelow(len(password)+1)
        char = secrets.choice(chars)
        new_pass = password[:pos] + char + password[pos:]
        # Randomly change case of some letters
        new_pass = ''.join(
            c.upper() if secrets.randbelow(2) else c.lower() if c.isalpha() else c
            for c in new_pass
        )
        variations.add(new_pass)
    return list(variations)


# Helper for password strength score

def password_strength_score(password):
    score = 0
    if len(password) >= MIN_LENGTH:
        score += 1
    if any(c.isupper() for c in password):
        score += 1
    if any(c.islower() for c in password):
        score += 1
    if any(c.isdigit() for c in password):
        score += 1
    if any(c in SPECIAL_CHARS for c in password):
        score += 1
    if len(password) >= 20:
        score += 1
    return min(score, 5)

# Pronounceable password generator (simple version)
def generate_pronounceable(length=12):
    vowels = 'aeiou'
    consonants = ''.join(set(string.ascii_lowercase) - set(vowels))
    pw = ''
    alt = True
    for i in range(length):
        if alt:
            pw += secrets.choice(consonants)
        else:
            pw += secrets.choice(vowels)
        alt = not alt
    # Randomly capitalize some letters
    pw = ''.join(c.upper() if secrets.randbelow(3)==0 else c for c in pw)
    # Add a digit and special char for strength
    pw += secrets.choice(string.digits)
    pw += secrets.choice(SPECIAL_CHARS)
    return pw

# Password history (session only)
app.secret_key = secrets.token_hex(16)

# Default password rotation period (days)
DEFAULT_ROTATION_DAYS = 90

@app.route('/download', methods=['POST'])
def download_password():
    pw = request.form.get('download_password', '')
    buf = io.BytesIO()
    buf.write(pw.encode('utf-8'))
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name='password.txt', mimetype='text/plain')

@app.route('/toggle_dark', methods=['POST'])
def toggle_dark():
    dark_mode = request.cookies.get('dark_mode', '0') == '1'
    resp = make_response(redirect(url_for('index')))
    resp.set_cookie('dark_mode', '0' if dark_mode else '1', max_age=60*60*24*365)
    return resp

def estimate_entropy(password, policy):
    charset = 0
    if policy.get('upper', True):
        charset += 26
    if policy.get('lower', True):
        charset += 26
    if policy.get('digits', True):
        charset += 10
    if policy.get('special', True):
        charset += len(SPECIAL_CHARS)
    if policy.get('exclude_similar', False):
        for c in 'lI1O0':
            if c in string.ascii_letters + string.digits:
                charset -= 1
    # Avoid negative/zero charset
    charset = max(charset, 1)
    entropy = len(password) * math.log2(charset)
    # Crack time: guesses per second (1e10 for offline, 1e6 for online)
    guesses = charset ** len(password)
    crack_time_seconds = guesses / 1e10
    return round(entropy, 2), crack_time_seconds

@app.route('/', methods=['GET', 'POST'])
def index():
    password = ''
    analysis = []
    custom = ''
    suggestions = []
    variations = []
    strength = 0
    history = session.get('history', [])
    show_pronounceable = False
    pronounceable = ''
    dark_mode = request.cookies.get('dark_mode', '0') == '1'
    app_name = "OpenPassGen"
    about = "OpenPassGen is an open-source, privacy-first password generator and analyzer. Built with Flask, designed for local use, and ready for the open-source community."
    rotation_days = DEFAULT_ROTATION_DAYS
    last_generated = session.get('last_generated', None)
    next_rotation = None
    entropy = None
    crack_time = None
    # Custom policy defaults
    policy = session.get('policy', {
        'min_length': MIN_LENGTH,
        'upper': True,
        'lower': True,
        'digits': True,
        'special': True,
        'exclude_similar': False
    })
    if request.method == 'POST':
        if 'set_policy' in request.form:
            policy['min_length'] = int(request.form.get('policy_min_length', MIN_LENGTH))
            policy['upper'] = 'policy_upper' in request.form
            policy['lower'] = 'policy_lower' in request.form
            policy['digits'] = 'policy_digits' in request.form
            policy['special'] = 'policy_special' in request.form
            policy['exclude_similar'] = 'policy_exclude_similar' in request.form
            session['policy'] = policy
        if 'generate' in request.form:
            length = int(request.form.get('length', policy['min_length']))
            use_upper = 'upper' in request.form if 'upper' in request.form else policy['upper']
            use_lower = 'lower' in request.form if 'lower' in request.form else policy['lower']
            use_digits = 'digits' in request.form if 'digits' in request.form else policy['digits']
            use_special = 'special' in request.form if 'special' in request.form else policy['special']
            chars = ''
            if use_upper:
                chars += string.ascii_uppercase
            if use_lower:
                chars += string.ascii_lowercase
            if use_digits:
                chars += string.digits
            if use_special:
                chars += SPECIAL_CHARS
            if policy['exclude_similar']:
                for c in 'lI1O0':
                    chars = chars.replace(c, '')
            if not chars:
                chars = string.ascii_letters
            password = ''.join(secrets.choice(chars) for _ in range(length))
            if 'shuffle' in request.form:
                password = ''.join(secrets.choice(password) for _ in range(len(password)))
            analysis = analyze_password(password)
            suggestions = suggest_enhancements(password)
            strength = password_strength_score(password)
            history.append(password)
            session['history'] = history[-5:]
            last_generated = datetime.now().strftime('%Y-%m-%d')
            session['last_generated'] = last_generated
            entropy, crack_time = estimate_entropy(password, policy)
        elif 'analyze' in request.form:
            custom = request.form.get('custom_password', '')
            analysis = analyze_password(custom)
            suggestions = suggest_enhancements(custom)
            password = custom
            strength = password_strength_score(custom)
            if custom:
                variations = generate_variations(custom)
                entropy, crack_time = estimate_entropy(custom, policy)
        elif 'pronounceable' in request.form:
            show_pronounceable = True
            pronounceable = generate_pronounceable()
    # Calculate next rotation date
    if last_generated:
        last_dt = datetime.strptime(last_generated, '%Y-%m-%d')
        next_rotation = (last_dt + timedelta(days=rotation_days)).strftime('%Y-%m-%d')
    return render_template('index.html', password=password, analysis=analysis, custom=custom, suggestions=suggestions, variations=variations, strength=strength, history=history[-5:], show_pronounceable=show_pronounceable, pronounceable=pronounceable, dark_mode=dark_mode, app_name=app_name, about=about, last_generated=last_generated, next_rotation=next_rotation, rotation_days=rotation_days, policy=policy, entropy=entropy, crack_time=crack_time)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
