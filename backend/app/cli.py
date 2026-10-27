import argparse
import getpass
import sys
from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash
from app.services.audit_service import record_audit_log
from app.db.seed import seed_database


def create_admin(email: str, name: str, password: str = None) -> None:
    """Create a new administrator account with Argon2id password hashing."""
    if not password:
        password = getpass.getpass("Enter administrator password (min 8 chars): ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Error: Passwords do not match.", file=sys.stderr)
            sys.exit(1)

    if len(password) < 8:
        print("Error: Password must be at least 8 characters long.", file=sys.stderr)
        sys.exit(1)

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email.lower().strip()).first()
        if existing:
            print(f"User '{email}' already exists. Updating role to administrator...")
            existing.role = "administrator"
            existing.status = "active"
            existing.hashed_password = get_password_hash(password)
            db.commit()
            print(f"Administrator '{email}' updated successfully.")
            return

        admin = User(
            name=name.strip(),
            email=email.lower().strip(),
            hashed_password=get_password_hash(password),
            role="administrator",
            status="active"
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

        record_audit_log(
            db=db,
            action="Administrator Created via CLI",
            record=f"CLI provisioning of administrator: {admin.email}",
            actor="CLI Tool",
            actor_id=admin.id,
            actor_role="administrator"
        )
        print(f"Administrator '{admin.name}' ({admin.email}) created successfully (ID: {admin.id}).")
    finally:
        db.close()


def run_seed() -> None:
    """Run database seeding for demo fixtures."""
    db = SessionLocal()
    try:
        seed_database(db)
        print("Database seeded with demonstration fixtures successfully.")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="SafePath Finder Administrative CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create-admin
    admin_parser = subparsers.add_parser("create-admin", help="Create or upgrade an administrator account")
    admin_parser.add_argument("--email", required=True, help="Administrator email address")
    admin_parser.add_argument("--name", default="Operations Administrator", help="Administrator display name")
    admin_parser.add_argument("--password", required=False, help="Administrator password (will prompt if omitted)")

    # seed
    subparsers.add_parser("seed", help="Seed database with pilot data sources and segments")

    args = parser.parse_args()
    if args.command == "create-admin":
        create_admin(args.email, args.name, args.password)
    elif args.command == "seed":
        run_seed()


if __name__ == "__main__":
    main()
