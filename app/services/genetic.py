import random
from datetime import datetime, date, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session
import numpy as np

from app.models.user import User, UserRole
from app.models.schedule import OfficeLocation
from app.schemas.schedule import GenerateScheduleRequest

def generate_work_schedule(db: Session, params: GenerateScheduleRequest) -> List[Dict[str, Any]]:
    """Generate work schedule using genetic algorithm"""
    
    # Get all active karyawan
    karyawan_list = db.query(User).filter(
        User.role == UserRole.KARYAWAN,
        User.is_active == True
    ).all()
    
    if not karyawan_list:
        raise ValueError("No active karyawan found")
    
    # Get all office locations
    office_locations = db.query(OfficeLocation).filter(
        OfficeLocation.is_active == True
    ).all()
    
    if not office_locations:
        raise ValueError("No active office locations found")
    
    # Generate dates range
    dates = []
    current_date = params.start_date
    while current_date <= params.end_date:
        dates.append(current_date)
        current_date += timedelta(days=1)
    
    # Initialize population
    population_size = min(params.population_size, 100)
    population = initialize_population(
        karyawan_list, dates, office_locations, population_size,
        params.min_wfo_per_week, params.max_wfo_per_week
    )
    
    # Evolution
    for generation in range(min(params.generations, 50)):
        # Calculate fitness
        fitness_scores = []
        for individual in population:
            fitness = calculate_fitness(
                individual, 
                params.office_capacity,
                params.min_wfo_per_week,
                params.max_wfo_per_week
            )
            fitness_scores.append(fitness)
        
        # Selection (elitism)
        elite_size = max(1, population_size // 10)
        elite_indices = np.argsort(fitness_scores)[-elite_size:]
        elite = [population[i] for i in elite_indices]
        
        # Selection for parents (tournament)
        parents = elite.copy()
        while len(parents) < population_size:
            tournament_size = 3
            tournament = random.sample(
                list(zip(population, fitness_scores)), 
                min(tournament_size, len(population))
            )
            tournament.sort(key=lambda x: x[1], reverse=True)
            parents.append(tournament[0][0])
        
        # Crossover
        offspring = []
        for i in range(0, len(parents), 2):
            if i + 1 < len(parents):
                parent1 = parents[i]
                parent2 = parents[i + 1]
                
                child1, child2 = uniform_crossover(parent1, parent2, karyawan_list, dates)
                offspring.extend([child1, child2])
        
        # Mutation
        population = []
        for child in offspring:
            if random.random() < params.mutation_rate:
                child = mutate(child, office_locations)
            population.append(child)
    
    # Return best individual
    final_fitness = []
    for individual in population:
        fitness = calculate_fitness(
            individual, 
            params.office_capacity,
            params.min_wfo_per_week,
            params.max_wfo_per_week
        )
        final_fitness.append(fitness)
    
    best_idx = np.argmax(final_fitness)
    best_schedule = population[best_idx]
    
    # CONVERT TO UPPERCASE sebelum return
    return convert_to_uppercase(best_schedule)

def initialize_population(karyawan_list, dates, office_locations, population_size, min_wfo_week, max_wfo_week):
    """Initialize population with random schedules"""
    population = []
    
    for _ in range(population_size):
        individual = []
        for karyawan in karyawan_list:
            emp_schedule = {
                "employee_id": karyawan.id,
                "employee_name": karyawan.full_name,
                "schedule": []
            }
            
            # Calculate target WFO days based on min/max per week
            total_weeks = len([d for d in dates if d.weekday() < 5]) / 5  # Weekdays only
            target_wfo_days = int((min_wfo_week + max_wfo_week) / 2 * total_weeks)
            
            wfo_count = 0
            
            for day_date in dates:
                # Skip weekends for OFF
                if day_date.weekday() >= 5:  # 5=Sabtu, 6=Minggu
                    work_status = "OFF"
                else:
                    # Assign based on target WFO days
                    if wfo_count < target_wfo_days and random.random() < 0.5:
                        work_status = "WFO"
                        wfo_count += 1
                    else:
                        work_status = "WFH"
                
                office_location_id = None
                office_location_name = None
                
                if work_status == "WFO" and office_locations:
                    office = random.choice(office_locations)
                    office_location_id = office.id
                    office_location_name = office.name
                
                emp_schedule["schedule"].append({
                    "date": day_date,
                    "work_status": work_status,
                    "office_location_id": office_location_id,
                    "office_location_name": office_location_name
                })
            
            individual.append(emp_schedule)
        
        population.append(individual)
    
    return population

def calculate_fitness(individual, office_capacity, min_wfo_per_week, max_wfo_per_week):
    """Calculate fitness score for an individual"""
    
    fitness = 100  # Base fitness
    
    for emp_schedule in individual:
        emp_wfo_count = 0
        total_weekdays = 0
        
        for day_schedule in emp_schedule["schedule"]:
            date = day_schedule["date"]
            
            # Count weekdays
            if date.weekday() < 5:
                total_weekdays += 1
            
            if day_schedule["work_status"] == "WFO":
                emp_wfo_count += 1
                
                # Check office capacity
                office_id = day_schedule["office_location_id"]
                
                if office_id:
                    # Count how many people in same office on same day
                    same_office_count = sum(
                        1 for other_emp in individual
                        for other_day in other_emp["schedule"]
                        if other_day["date"] == date and 
                        other_day["office_location_id"] == office_id and
                        other_day["work_status"] == "WFO"
                    )
                    
                    if same_office_count > office_capacity:
                        fitness -= 5  # Penalty for overcapacity
        
        # Calculate WFO per week
        if total_weekdays > 0:
            wfo_per_week = (emp_wfo_count / total_weekdays) * 5
            
            # Penalize if outside min/max range
            if wfo_per_week < min_wfo_per_week:
                fitness -= (min_wfo_per_week - wfo_per_week) * 3
            elif wfo_per_week > max_wfo_per_week:
                fitness -= (wfo_per_week - max_wfo_per_week) * 3
    
    # Add randomness for diversity
    fitness += random.uniform(-10, 10)
    
    return max(fitness, 0)

def uniform_crossover(parent1, parent2, karyawan_list, dates):
    """Uniform crossover between two parents"""
    child1 = []
    child2 = []
    
    for emp1, emp2 in zip(parent1, parent2):
        child1_schedule = {
            "employee_id": emp1["employee_id"],
            "employee_name": emp1["employee_name"],
            "schedule": []
        }
        child2_schedule = {
            "employee_id": emp2["employee_id"],
            "employee_name": emp2["employee_name"],
            "schedule": []
        }
        
        for day1, day2 in zip(emp1["schedule"], emp2["schedule"]):
            if random.random() < 0.5:
                child1_schedule["schedule"].append(day1.copy())
                child2_schedule["schedule"].append(day2.copy())
            else:
                child1_schedule["schedule"].append(day2.copy())
                child2_schedule["schedule"].append(day1.copy())
        
        child1.append(child1_schedule)
        child2.append(child2_schedule)
    
    return child1, child2

def mutate(individual, office_locations):
    """Mutate an individual"""
    mutated = []
    
    for emp_schedule in individual:
        mutated_schedule = {
            "employee_id": emp_schedule["employee_id"],
            "employee_name": emp_schedule["employee_name"],
            "schedule": []
        }
        
        for day_schedule in emp_schedule["schedule"]:
            # Skip weekends (always OFF)
            if day_schedule["date"].weekday() >= 5:
                mutated_schedule["schedule"].append({
                    "date": day_schedule["date"],
                    "work_status": "OFF",
                    "office_location_id": None,
                    "office_location_name": None
                })
                continue
                
            # Small chance to flip work status
            if random.random() < 0.1:  # 10% mutation chance per day
                # Toggle between WFO and WFH only (not OFF on weekdays)
                if day_schedule["work_status"] == "WFO":
                    new_status = "WFH"
                else:
                    new_status = "WFO"
                    
                new_office_id = None
                new_office_name = None
                
                if new_status == "WFO" and office_locations:
                    office = random.choice(office_locations)
                    new_office_id = office.id
                    new_office_name = office.name
                
                mutated_schedule["schedule"].append({
                    "date": day_schedule["date"],
                    "work_status": new_status,
                    "office_location_id": new_office_id,
                    "office_location_name": new_office_name
                })
            else:
                mutated_schedule["schedule"].append(day_schedule.copy())
        
        mutated.append(mutated_schedule)
    
    return mutated

def convert_to_uppercase(schedule_data):
    """Convert all work_status to uppercase"""
    converted = []
    
    for emp_schedule in schedule_data:
        converted_schedule = {
            "employee_id": emp_schedule["employee_id"],
            "schedule": []
        }
        
        for day_schedule in emp_schedule["schedule"]:
            # Convert work_status to uppercase
            work_status = str(day_schedule["work_status"]).upper()
            
            # Validate work status
            if work_status not in ["WFO", "WFH", "OFF"]:
                # Default based on day
                if day_schedule["date"].weekday() >= 5:
                    work_status = "OFF"
                else:
                    work_status = "WFH"
            
            converted_schedule["schedule"].append({
                "date": day_schedule["date"],
                "work_status": work_status,
                "office_location_id": day_schedule["office_location_id"]
            })
        
        converted.append(converted_schedule)
    
    return converted