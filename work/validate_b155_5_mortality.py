#!/usr/bin/env python3
"""Validate and report the B155.5 full-game mortality calibration."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from pathlib import Path

from patch_mobile_furniture_pack import (
    OLDER_MORTALITY_HAZARD_CAP_MILLIONTHS,
    OLDER_MORTALITY_RANDOM_LIMIT,
    OLDER_MORTALITY_TABLE_FIRST_AGE,
    older_mortality_hazard_millionths,
    older_mortality_survival_probability_through_age,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "outputs"
FULL_GAME_ADULTS = 30 * 2
DEFAULT_SIMULATION_PEOPLE = 1_000_000
DEFAULT_SEED = 0xB1555001
REPORT_AGES = (55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110, 115, 120, 122)


def reach_probability(age: int, active_food_groups: int) -> float:
    """Probability one adult reaches a birthday before that birthday's roll."""
    return older_mortality_survival_probability_through_age(
        age - 1, active_food_groups
    )


def at_least_one_probability(single_probability: float, people: int) -> float:
    if single_probability <= 0.0:
        return 0.0
    if single_probability >= 1.0:
        return 1.0
    return -math.expm1(people * math.log1p(-single_probability))


def exact_age_death_probability(age: int, active_food_groups: int) -> float:
    effective_age = age - max(0, min(4, active_food_groups))
    hazard = older_mortality_hazard_millionths(effective_age)
    return reach_probability(age, active_food_groups) * (
        hazard / OLDER_MORTALITY_RANDOM_LIMIT
    )


def mode_and_median(active_food_groups: int) -> tuple[int, int]:
    rows = []
    median = None
    for age in range(55, 501):
        death = exact_age_death_probability(age, active_food_groups)
        rows.append((death, age))
        survival_after = older_mortality_survival_probability_through_age(
            age, active_food_groups
        )
        if median is None and survival_after <= 0.5:
            median = age
    return max(rows)[1], median


def validate_curve() -> None:
    assert older_mortality_hazard_millionths(55) == 0
    hazards = [older_mortality_hazard_millionths(age) for age in range(55, 501)]
    assert hazards == sorted(hazards)
    assert all(0 <= value <= OLDER_MORTALITY_HAZARD_CAP_MILLIONTHS for value in hazards)
    assert older_mortality_hazard_millionths(317) < OLDER_MORTALITY_HAZARD_CAP_MILLIONTHS
    assert older_mortality_hazard_millionths(318) == OLDER_MORTALITY_HAZARD_CAP_MILLIONTHS
    assert older_mortality_hazard_millionths(500) < OLDER_MORTALITY_RANDOM_LIMIT

    for groups in range(5):
        mode, median = mode_and_median(groups)
        assert mode == 72 + groups
        assert median == 74 + groups
        for age in REPORT_AGES:
            shifted_age = age - groups
            assert math.isclose(
                reach_probability(age, groups),
                reach_probability(shifted_age, 0),
                rel_tol=0.0,
                abs_tol=1e-15,
            )

    game_110_zero = at_least_one_probability(reach_probability(110, 0), FULL_GAME_ADULTS)
    game_110_four = at_least_one_probability(reach_probability(110, 4), FULL_GAME_ADULTS)
    game_122_zero = at_least_one_probability(reach_probability(122, 0), FULL_GAME_ADULTS)
    game_122_four = at_least_one_probability(reach_probability(122, 4), FULL_GAME_ADULTS)
    assert 0.23 < game_110_zero < 0.24
    assert 0.43 < game_110_four < 0.44
    assert 0.00035 < game_122_zero < 0.00037
    assert 0.0088 < game_122_four < 0.0091


def simulate_reaching_122(people: int, seed: int) -> list[dict[str, float | int]]:
    results = []
    for groups in range(5):
        probability = reach_probability(122, groups)
        rng = random.Random(seed + groups)
        alive = sum(rng.random() < probability for _ in range(people))
        expected = people * probability
        variance = people * probability * (1.0 - probability)
        z_score = (alive - expected) / math.sqrt(variance) if variance else 0.0
        assert abs(z_score) < 5.0
        results.append(
            {
                "active_food_groups": groups,
                "people": people,
                "survivors_reaching_122": alive,
                "analytical_expected_survivors": expected,
                "z_score": z_score,
            }
        )
    return results


def build_rows() -> list[dict[str, float | int]]:
    rows = []
    for groups in range(5):
        for age in REPORT_AGES:
            reach = reach_probability(age, groups)
            death = exact_age_death_probability(age, groups)
            full_game_reach = at_least_one_probability(reach, FULL_GAME_ADULTS)
            full_game_death = at_least_one_probability(death, FULL_GAME_ADULTS)
            effective_age = age - groups
            rows.append(
                {
                    "age": age,
                    "active_food_groups": groups,
                    "annual_hazard": (
                        older_mortality_hazard_millionths(effective_age)
                        / OLDER_MORTALITY_RANDOM_LIMIT
                    ),
                    "per_adult_reach_probability": reach,
                    "full_game_at_least_one_reaches_probability": full_game_reach,
                    "expected_games_per_reach": (
                        1.0 / full_game_reach if full_game_reach else math.inf
                    ),
                    "per_adult_exact_age_death_probability": death,
                    "expected_exact_age_deaths_per_60": FULL_GAME_ADULTS * death,
                    "full_game_at_least_one_exact_age_death_probability": full_game_death,
                }
            )
    return rows


def write_reports(output_dir: Path, rows: list[dict], simulation: list[dict]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "B155.5-mortality-full-game-calibration.csv"
    json_path = output_dir / "B155.5-mortality-full-game-calibration.json"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "build": "B155.5",
        "full_game_adults": FULL_GAME_ADULTS,
        "formula": (
            "n=max(0, displayedAge-(55+clamp(activeFoodGroups,0,4))); "
            "intensity=0.00365*n+0.06*max(0,n-55); "
            "hazard=min(0.999999,1-exp(-intensity)) rounded half-up to millionths"
        ),
        "birthday_semantics": (
            "reaching age A means surviving every old-age roll through age A-1"
        ),
        "simulation": simulation,
        "rows": rows,
    }
    json_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(csv_path)
    print(json_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--simulation-people", type=int, default=DEFAULT_SIMULATION_PEOPLE)
    parser.add_argument("--seed", type=lambda value: int(value, 0), default=DEFAULT_SEED)
    args = parser.parse_args()

    validate_curve()
    rows = build_rows()
    simulation = simulate_reaching_122(args.simulation_people, args.seed)
    write_reports(args.output_dir, rows, simulation)
    print("B155.5 mortality calibration validated")


if __name__ == "__main__":
    main()
