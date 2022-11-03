import os
import random

from flask import *
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
from sqlalchemy import create_engine, types



app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///f1.db"
db = SQLAlchemy(app)
NUM_COLORS = 20
db_url = os.environ.get("DATABASE_URL")
db_url = db_url.replace("postgres","postgresql")
engine = create_engine(db_url)


def get_laptimes(raceId):
    race_laptimes = pd.read_sql(
        "select l.raceId as ""RaceId"", concat(d.firstname, ' ',d.lastname) as ""Name"", l.lap as ""Lap"",l.lap_position as ""Position"", l.lap_time as ""Time"",l.milliseconds as ""Time_MS"" from lap_times l natural inner join driver d "
        "where l.raceId in (select raceId from race where raceId in (select raceId from results where raceId = '" + raceId + "'));",
        engine)
    race_laptimes['time_ms'] = race_laptimes['time_ms'].astype(int)
    race_laptimes['name'] = race_laptimes['name'].astype(str)
    race_laptimes['time_ms'] = race_laptimes['time_ms']/1000
    laps = race_laptimes['lap'].unique().tolist()
    drivers = pd.unique(race_laptimes['name'])
    lap_data = {'label': laps,'data':[{'data': race_laptimes.loc[race_laptimes['name']==str(driver),'time_ms'].values.tolist(), 'label': str(driver), 'borderColor': "#"+''.join([random.choice('0123456789ABCDEF') for j in range(6)]), 'fill': False } for driver in drivers]}
    return lap_data




def get_qualy_comparisons(raceId):
    curr_race = pd.read_sql("select q.constructorid, avg( "
                            "case when q.q3 is null and q.q2 is null then extract(EPOCH from q.q1)when q.q3 is null and q.q2 is not null then extract(EPOCH from q.q2) else extract(EPOCH from q.q3) end )" 
                            " from qualifying q where q.raceId = '" + raceId +"' group by q.constructorid",engine)

    last_race = pd.read_sql(" select q.constructorid, avg(case "
                            "when q.q3 is null and q.q2 is null then extract(EPOCH from q.q1) "
                            "when q.q3 is null and q.q2 is not null then extract(EPOCH from q.q2) "
                            " else extract(EPOCH from q.q3) "
                            "end) from qualifying q natural inner join race r "
                            "where r.circuitname in (select circuitname from race r1 where r1.raceId='"+raceId +"')"
                            "and r.raceId in (select raceId from race r2 where r2.raceId<>'" + raceId +"' and r2.circuitname=r.circuitname order by r2.year desc limit 1) group by q.constructorid", engine)

    constructors_df = pd.read_sql(" select constructorid, name from constructors",engine)
    last_race_grouped = last_race.merge(constructors_df, on="constructorid",how="inner")
    curr_race_grouped = curr_race.merge(constructors_df, on="constructorid",how="inner")
    qualy_gains_df = last_race_grouped.merge(curr_race_grouped,on="constructorid",how="inner")
    qualy_gains_df['time_diff'] = qualy_gains_df['avg_y'] - qualy_gains_df['avg_x']
    qualy_gains_df.drop(columns='name_y',inplace=True)
    qualy_gains_df.rename(columns = {'avg_x':'last_race','avg_y':'curr_race','name_x':'name'},inplace=True)
    teams = qualy_gains_df['name'].unique().tolist()
    qualy_json = [{'x': str(data),'y': qualy_gains_df.loc[qualy_gains_df['name']==str(data),'time_diff'].values} for data in teams]
    return qualy_json


@app.route("/",methods=["GET","POST"])
def home():
    if request.method=="GET":
        races_2022 = pd.read_sql("select r.raceId, r.name ""Race"", r.circuitname ""Circuit"" from race r where year = 2022 order by r.race_date",engine)
        return render_template("index.html", race_details=races_2022, display=False)
    elif request.method=="POST":
        raceId = request.form.get('race')
        race_details = pd.read_sql("select r.year ""race_year"", r.name ""Race"", r.circuitname ""Circuit"" from race r where raceId='" + raceId + "';",engine)
        race_results_df = pd.read_sql("select r.positiontext ""Position"", d.firstname || ' ' || d.lastname ""Driver"", c.name ""Team"", r.points ""Points"", r.status ""Status""  from results r natural inner JOIN "
                                      "driver d "  
                                      "natural inner join constructors c where r.raceId = '" + raceId + "' "
                                      "order by r.positionorder asc limit 20;",engine)
        race_details = race_details.to_dict()
        lap_data = get_laptimes(raceId)
        qualy_diff = get_qualy_comparisons(raceId)
        return_obj = {
            "Results": race_results_df,
            "Lap_Data": lap_data,
            "Race_Name": race_details,
            'Qualy_Diff': qualy_diff
        }
        races_2022 = pd.read_sql(
            "select r.raceId, r.name ""Race"", r.circuitname ""Circuit"" from race r where year = 2022 order by r.race_date",
            engine)
        return render_template("index.html",races =return_obj,display=True,race_details=races_2022)

@app.route("/drivers-championship",methods=["GET","POST"])
def driversChampionship():
    if request.method=="GET":
        drivers_2022 = pd.read_sql("select d.driverid ""driverid"", d.firstname || ' ' || d.lastname ""drivername""  from driver d where d.driverid in ("
            "select distinct driverid from results where raceid in (select raceid from race where year=2022))",engine)
        return render_template("drivers.html", driver_details=drivers_2022, display=False)

    else:
        driver_1 =  request.form.get('driver_1')
        driver_2 = request.form.get('driver_2')
        driver_1_points = pd.read_sql("with data as ("
    "select driverid,raceid, sum(points) ""points"" from results where raceid in (select raceid from race where year=2022 order by race_date) and driverid in ('" + driver_1 + "')"
    "group by driverid, raceid"
    ")"
    "select "
    "driverid, round, firstname || ' ' || lastname ""drivername"", "
    "sum(points) over (order by raceid asc rows between unbounded preceding and current row)"
    "from data natural join race natural join driver order by round asc",engine)

        driver_2_points = pd.read_sql("with data as ("
                                      "select driverid,raceid, sum(points) ""points"" from results where raceid in (select raceid from race where year=2022 order by race_date) and driverid in ('" + driver_2 + "')"
                                     "group by driverid, raceid"
                                     ")"
                                    "select "
                                    "driverid, round, firstname || ' ' || lastname ""drivername"", "
                                    "sum(points) over (order by raceid asc rows between unbounded preceding and current row)"
                                    "from data natural join race natural join driver order by round asc",
                                      engine)

        driver_1_points = driver_1_points.append(driver_2_points)
        rounds = driver_1_points['round'].unique().tolist()
        drivers = pd.unique(driver_1_points['drivername'])
        driver_data = {'label': rounds, 'data': [
            {'data': driver_1_points.loc[driver_1_points['drivername'] == str(driver), 'sum'].values.tolist(),
             'label': str(driver), 'borderColor': "#" + ''.join([random.choice('0123456789ABCDEF') for j in range(6)]),
             'fill': False} for driver in drivers]}
        drivers_2022 = pd.read_sql(
            "select d.driverid ""driverid"", d.firstname || ' ' || d.lastname ""drivername""  from driver d where d.driverid in ("
            "select distinct driverid from results where raceid in (select raceid from race where year=2022))", engine)
        return render_template("drivers.html",display = True,drivers_data = driver_data, driver_details = drivers_2022)

if __name__=='__main__':
    app.run(debug=True)