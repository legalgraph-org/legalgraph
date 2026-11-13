"""checklist: what a business must do, given facts about it."""

from pathlib import Path

import click
from rdflib import SKOS, Graph

from legalgraph import LG, LGO, LGV, rules, scenarios
from legalgraph.cli.main import cli, load_data
from legalgraph.load import Sources


def show_questions(conditions: dict[str, rules.Condition], places: dict[str, str]) -> None:
    click.echo(f"--established-in, --market: one of {', '.join(sorted(places))}")
    for condition in rules.asked(conditions):
        click.echo(f"{condition.id}: {condition.question}")


def show_obligations(
    graph: Graph, found: list[rules.Obligation], established_in: str | None, offered: set[str], places: dict[str, str]
) -> None:
    labels = {
        str(s): str(o) for s, o in graph.subject_objects(SKOS.prefLabel) if getattr(o, "language", None) in (None, "en")
    }
    citations = {str(s): str(o) for s, o in graph.subject_objects(LGO.citation)}

    def cited(provisions: list[str]) -> str:
        return ", ".join(citations.get(f"{LG}{p}", p) for p in provisions)

    for obligation in found:
        status = "" if obligation.status == "Reviewed" else " (draft)"
        click.echo(click.style(f"{obligation.applies_in} · {obligation.label}{status}", bold=True))
        for item in obligation.items:
            click.echo(f"  disclose: {labels.get(f'{LGV}{item}', item)}")
        for action in obligation.actions:
            click.echo(f"  do: {labels.get(f'{LGV}{action}', action)}")
        for place, national in rules.national(obligation, established_in, offered).items():
            click.echo(f"  in {places[place]}: {cited(national)}")
        click.echo(click.style(f"  {cited(obligation.established_by)} · lg:{obligation.id}", dim=True))
    if not found:
        click.echo("No obligation applies to these facts.")


@cli.command()
@click.option("--fact", "-f", "facts", multiple=True, help="A condition that holds, e.g. SellsToConsumers. Repeatable.")
@click.option("--established-in", "-e", help="Where the business is established, as a jurisdiction code, e.g. AT.")
@click.option(
    "--market", "-m", "markets", multiple=True, help="Where it offers goods or services, e.g. EU or FR. Repeatable."
)
@click.option(
    "--scenario",
    "-s",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="A scenario file (scenarios/*.yaml) whose facts to use.",
)
@click.option("--questions", is_flag=True, help="List the conditions and the question for each, then exit.")
@click.pass_obj
def checklist(
    sources: Sources,
    facts: tuple[str, ...],
    established_in: str | None,
    markets: tuple[str, ...],
    scenario: Path | None,
    questions: bool,
) -> None:
    """What a business must do, given facts about it: the obligations of the rules layer that apply,
    with the information to disclose, the actions to take and the provisions behind each."""
    graph = load_data(sources, with_ontology=True)
    conditions, obligations = rules.load(graph)
    places = rules.jurisdictions(graph)
    if questions:
        show_questions(conditions, places)
        return
    given, offered = set(facts), set(markets)
    if scenario:
        loaded = scenarios.load_scenario(scenario)
        given |= loaded.facts
        offered |= loaded.markets
        established_in = established_in or loaded.established_in
    unknown = ({established_in} - {None} | offered) - set(places)
    if unknown:
        raise click.ClickException(f"Unknown jurisdiction(s): {', '.join(sorted(unknown))}")
    try:
        found = rules.applicable(conditions, obligations, given, established_in, offered)
    except rules.RulesError as error:
        raise click.ClickException(f"{error}. List them with `legalgraph checklist --questions`.") from error
    show_obligations(graph, found, rules.establishment(conditions, given, established_in), offered, places)
