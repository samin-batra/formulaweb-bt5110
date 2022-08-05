import sqlite3
import random

from flask import *
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
import json


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///f1.db"
db = SQLAlchemy(app)
NUM_COLORS = 20


class Races(db.Model):
    raceId = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer)
    round = db.Column(db.Integer)
    circuitId = db.Column(db.Integer)
    name = db.Column(db.String(200))
    date = db.Column(db.String(200))
    time = db.Column(db.String(200))
    url = db.Column(db.String(300))
    fp1_date = db.Column(db.String(50))
    fp1_time = db.Column(db.String(50))
    fp2_date = db.Column(db.String(50))
    fp2_time = db.Column(db.String(50))
    fp3_date = db.Column(db.String(50))
    fp3_time = db.Column(db.String(50))
    quali_date = db.Column(db.String(50))
    quali_time = db.Column(db.String(50))
    sprint_date = db.Column(db.String(50))
    sprint_time = db.Column(db.String(50))


class Circuits(db.Model):
    circuitId = db.Column(db.Integer, primary_key=True)
    circuitRef = db.Column(db.Text)
    name = db.Column(db.Text)
    location = db.Column(db.Text)
    country = db.Column(db.Text)
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    alt = db.Column(db.Text)
    url = db.Column(db.Text)


class Results(db.Model):
    raceId = db.Column(db.Integer)
    resultId = db.Column(db.Integer, primary_key=True)
    driverId = db.Column(db.Integer)
    constructorId = db.Column(db.Integer)
    number = db.Column(db.Text)
    grid = db.Column(db.Integer)
    position = db.Column(db.Text)
    positionText = db.Column(db.Text)
    positionOrder = db.Column(db.Text)
    points = db.Column(db.Float)
    laps = db.Column(db.Integer)
    time = db.Column(db.Text)
    milliseconds = db.Column(db.Text)
    fastestLap = db.Column(db.Text)
    rank = db.Column(db.Text)
    fastestLapTime = db.Column(db.Text)
    fastestLapSpeed = db.Column(db.Text)
    statusId = db.Column(db.Integer)


def get_laptimes(connection):
    race_laptimes = pd.read_sql("select l.raceId as RaceId, d.forename || ' ' || d.surname as Name, l.lap as Lap, l.position as Position, l.time as Time, l.milliseconds as Time_MS from lap_times l "
                    "inner join drivers d on l.driverId=d.driverId " 
                    "where l.raceId in ( "
                    "select raceId from races where raceId in "
                    "(select raceId from results order by raceId desc limit 1))" ,connection)
    race_laptimes['Time_MS'] = race_laptimes['Time_MS'].astype(int)
    race_laptimes['Name'] = race_laptimes['Name'].astype(str)
    race_laptimes['Time_MS'] = race_laptimes['Time_MS']/1000
    laps = race_laptimes['Lap'].unique().tolist()
    drivers = pd.unique(race_laptimes['Name'])
    lap_data = {'label': laps,'data':[{'data': race_laptimes.loc[race_laptimes['Name']==str(driver),'Time_MS'].values.tolist(), 'label': str(driver), 'borderColor': "#"+''.join([random.choice('0123456789ABCDEF') for j in range(6)]), 'fill': False } for driver in drivers]}
    return lap_data


def format_laptimes(df):
    df.drop(labels=['qualifyId','raceId','driverId'],axis=1)
    df.loc[df['q1']=='\\N','q1'] = '-1'
    df.loc[df['q2'] == '\\N', 'q2'] = '-1'
    df.loc[df['q3'] == '\\N', 'q3'] = '-1'
    df.loc[df['q2']=='-1','q3'] = df['q1']
    df.loc[df['q3']=='-1','q3'] = df['q2']
    q_split = df.loc[df['q3']!='-1','q3'].str.split(":",expand = True)
    q_min = pd.to_numeric(q_split[0])
    q_secs = pd.to_numeric(q_split[1])
    df['q3'] = q_min*60 + q_secs
    return df


def get_qualy_comparisons(connection):
    last_race = pd.read_sql("select * from qualifying where raceId in ("
                            "select raceId from races where circuitId in "
                            "(select circuitId from races where raceId in (select raceId from results order by raceId desc limit 1)) "
                            "order by raceId desc"
                            " limit 1 offset 1)",connection)

    curr_race = pd.read_sql(" select * from qualifying where raceId in ( "
                            " select raceId from races where raceId in "
                            " (select raceId from results order by raceId desc limit 1) "
                            ")", connection)

    constructors_df = pd.read_sql(" select constructorId, name from constructors",connection, index_col="constructorId")
    last_race = format_laptimes(last_race)
    curr_race = format_laptimes(curr_race)
    last_race_grouped = last_race.groupby(['constructorId']).agg({'q3':'mean'})
    curr_race_grouped = curr_race.groupby(['constructorId']).agg({'q3':'mean'})
    last_race_grouped = last_race_grouped.join(constructors_df, on="constructorId",how="inner")
    curr_race_grouped = curr_race_grouped.join(constructors_df, on="constructorId",how="inner")
    qualy_gains_df = last_race_grouped.join(curr_race_grouped,on="constructorId",how="inner",lsuffix='last_race',rsuffix='curr_race')
    qualy_gains_df['time_diff'] = qualy_gains_df['q3curr_race'] - qualy_gains_df['q3last_race']
    qualy_gains_df.drop(columns='namelast_race',inplace=True)
    qualy_gains_df.rename(columns = {'q3last_race':'last_race','q3curr_race':'curr_race','namecurr_race':'name'},inplace=True)
    teams = qualy_gains_df['name'].unique().tolist()
    qualy_json = [{'x': str(data),'y': qualy_gains_df.loc[qualy_gains_df['name']==str(data),'time_diff'].values} for data in teams]
    return qualy_json


@app.route("/")
def home():
    connection = sqlite3.connect("f1.db")
    latest_race = Results.query.order_by(Results.resultId.desc()).first()
    res = Races.query.get(latest_race.raceId)
    result = Results.query.order_by(Results.resultId.desc()).first()
    race_results_df = pd.read_sql("select r.position as Position, d.forename || ' ' || d.surname as Name, "
                                  "c.name as Team, r.points as Points from results r inner JOIN "
                                  "drivers d on r.driverId=d.driverId "
                                  "inner join constructors c "
                                  "on c.constructorId=r.constructorId "
                                  "order by r.raceId desc limit 20;",connection)
    lap_data = get_laptimes(connection)
    qualy_diff = get_qualy_comparisons(connection)
    return_obj = {
        "Results": race_results_df,
        "Lap_Data": lap_data,
        "Race_Name": res.name,
        'Qualy_Diff': qualy_diff
    }
    return render_template("index.html",races =return_obj)


if __name__=='__main__':
    app.run(debug=True)