import sys
import click
from app import create_app, db
from app.models import User

app = create_app()


@app.cli.command("create-user")
@click.argument("username")
@click.argument("password")
@click.argument("name", default="")
def create_user(username, password, name):
    """Создать нового пользователя. Пример: python run.py create-user admin pass123 'Иван'"""
    with app.app_context():
        if User.query.filter_by(username=username).first():
            print(f"Ошибка: пользователь '{username}' уже существует")
            return
        user = User(username=username, display_name=name or username)
        user.set_password(password)
        if "admin" in username.lower() and not User.query.filter_by(role="admin").first():
            user.role = "admin"
        db.session.add(user)
        db.session.commit()
        role_label = " (ADMIN)" if user.role == "admin" else ""
        print(f"✅ Пользователь создан: {username}{role_label}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "create-user":
        # Fallback if click isn't available
        username = sys.argv[2] if len(sys.argv) > 2 else ""
        password = sys.argv[3] if len(sys.argv) > 3 else ""
        name = sys.argv[4] if len(sys.argv) > 4 else ""
        if not username or not password:
            print("Usage: python run.py create-user <username> <password> [name]")
            sys.exit(1)
        with app.app_context():
            if User.query.filter_by(username=username).first():
                print(f"Пользователь '{username}' уже существует")
                sys.exit(1)
            user = User(username=username, display_name=name or username)
            user.set_password(password)
            if "admin" in username.lower() and not User.query.filter_by(role="admin").first():
                user.role = "admin"
            db.session.add(user)
            db.session.commit()
            print(f"Пользователь создан: {username} (ROLE: {user.role})")
    else:
        app.run(host="0.0.0.0", port=8080, debug=True)