"""hygiene: the repository's own conventions, beyond what ruff and SHACL check."""

import click

from legalgraph import hygiene
from legalgraph.cli.main import cli
from legalgraph.load import REPO_ROOT


@cli.command("hygiene")
@click.argument("codes", nargs=-1)
@click.option("--rules", "list_rules", is_flag=True, help="List the rules and exit.")
def hygiene_command(codes: tuple[str, ...], list_rules: bool) -> None:
    """Check the project's conventions (all rules, or the given codes such as PY001 ONT002)."""
    if list_rules:
        for rule in hygiene.RULES:
            click.echo(f"{rule.code}  {rule.summary}")
        return
    unknown = set(codes) - {rule.code for rule in hygiene.RULES}
    if unknown:
        raise click.ClickException(f"Unknown rule(s): {', '.join(sorted(unknown))}; see --rules")
    findings = hygiene.check(REPO_ROOT, set(codes) or None)
    for finding in findings:
        click.echo(f"✘ {finding.show(REPO_ROOT)}", err=True)
    if findings:
        raise click.ClickException(f"{len(findings)} hygiene problem(s) found.")
    click.echo(f"✔ The project follows its {len(hygiene.RULES)} hygiene rules.")
