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


def refresh_network(force: bool = True) -> None:
    """Download and refresh the genuine OpenStreetMap pedestrian network for the active study area."""
    from app.geospatial.study_area import StudyArea
    from app.geospatial.network_adapter import OsmNetworkAdapter

    study_area = StudyArea.from_settings()
    print(f"Retrieving genuine pedestrian street network for '{study_area.name}' [bbox: {study_area.bbox}] via OSMnx...")
    adapter = OsmNetworkAdapter()
    result = adapter.get_pedestrian_network(study_area, force_reload=force)
    print(f"Network successfully installed and cached:")
    print(f"  Study Area: {result.study_area_name}")
    print(f"  Nodes: {result.nodes_count}")
    print(f"  Edges: {result.edges_count}")
    print(f"  Connected components: {result.connected_components_count}")
    print(f"  Cache path: {result.cache_path}")
    print(f"  Attribution: {result.attribution}")


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

    # refresh-network
    net_parser = subparsers.add_parser("refresh-network", help="Download and cache genuine OSM pedestrian network")
    net_parser.add_argument("--force", action="store_true", default=True, help="Force re-download from Overpass API")

    args = parser.parse_args()
    if args.command == "create-admin":
        create_admin(args.email, args.name, args.password)
    elif args.command == "seed":
        run_seed()
    elif args.command == "refresh-network":
        refresh_network(args.force)


if __name__ == "__main__":
    main()
