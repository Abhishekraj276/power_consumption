# app.py
from flask import Flask, render_template, request
import pandas as pd
import numpy as np
import joblib
import os
from datetime import datetime

app = Flask(__name__)


model_exists = os.path.exists('energy_forecast_model.pkl') and os.path.exists('scaler.pkl')


expected_features = [
    'Temperature', 'Humidity', 'SquareFootage', 'Occupancy', 'HVACUsage', 
    'LightingUsage', 'RenewableEnergy', 'DayOfWeek', 'Holiday', 'Hour', 
    'DayOfMonth', 'Month', 'WeekOfYear', 'IsWeekend', 'Season', 
    'Energy_Lag_24h', 'Energy_Lag_168h', 'Energy_MA_24h', 'Energy_MA_7d'
]

if model_exists:
    try:
        model = joblib.load('energy_forecast_model.pkl')
        scaler = joblib.load('scaler.pkl')
        print("Model loaded successfully")
        
       
        try:
            if hasattr(model, 'feature_names_in_'):
                expected_features = list(model.feature_names_in_)
            elif hasattr(scaler, 'feature_names_in_'):
                expected_features = list(scaler.feature_names_in_)
            print(f"Model expects {len(expected_features)} features: {expected_features}")
        except:
            print(f"Using feature names from error: {expected_features}")
            
    except Exception as e:
        model_exists = False
        print(f"Error loading model files: {e}")
else:
    print("Model files not found. Running in demo mode.")

def create_features_from_input(form_data, current_time):
    """Create all required features from form input in the exact order"""
    features = {}

    features['Temperature'] = float(form_data.get('temperature', 22.0))
    features['Humidity'] = float(form_data.get('humidity', 50.0))
   
    features['SquareFootage'] = float(form_data.get('square_footage', 2000.0))
    features['Occupancy'] = float(form_data.get('occupancy', 3.0))
 
    features['HVACUsage'] = float(form_data.get('hvac_usage', 15.0))
    features['LightingUsage'] = float(form_data.get('lighting_usage', 8.0))
    features['RenewableEnergy'] = float(form_data.get('renewable_energy', 5.0))
 
    features['DayOfWeek'] = int(form_data.get('day_of_week', current_time.weekday()))
    features['Holiday'] = float(form_data.get('holiday', 0.0))  # 0=No, 1=Yes
    features['Hour'] = int(form_data.get('hour', current_time.hour))
    features['DayOfMonth'] = int(form_data.get('day_of_month', current_time.day))
    features['Month'] = int(form_data.get('month', current_time.month))

    week_of_year = current_time.isocalendar()[1]
    features['WeekOfYear'] = int(form_data.get('week_of_year', week_of_year))
  
    features['IsWeekend'] = 1.0 if features['DayOfWeek'] in [5, 6] else 0.0
    
    month = features['Month']
    if month in [12, 1, 2]:
        features['Season'] = 0.0  # Winter
    elif month in [3, 4, 5]:
        features['Season'] = 1.0  # Spring
    elif month in [6, 7, 8]:
        features['Season'] = 2.0  # Summer
    else:
        features['Season'] = 3.0  # Fall
  
    base_energy = float(form_data.get('base_energy', 100.0))
    features['Energy_Lag_24h'] = float(form_data.get('energy_lag_24h', base_energy))
    features['Energy_Lag_168h'] = float(form_data.get('energy_lag_168h', base_energy * 0.95))
    features['Energy_MA_24h'] = float(form_data.get('energy_ma_24h', base_energy * 1.05))
    features['Energy_MA_7d'] = float(form_data.get('energy_ma_7d', base_energy * 1.02))
    
    final_features = []
    for feature in expected_features:
        if feature in features:
            final_features.append(features[feature])
        else:
          
            if 'Energy' in feature:
                final_features.append(base_energy * (0.9 + np.random.random() * 0.2))
            elif any(x in feature for x in ['Temp', 'Humid']):
                final_features.append(22.0 if 'Temp' in feature else 50.0)
            elif 'Usage' in feature:
                final_features.append(10.0 + np.random.random() * 5.0)
            else:
                final_features.append(0.0)
    
    return final_features

@app.route('/')
def index():
    now = datetime.now()
    week_of_year = now.isocalendar()[1]
    return render_template('index.html', model_exists=model_exists, 
                         feature_names=expected_features, now=now,
                         week_of_year=week_of_year,
                         feature_count=len(expected_features))

@app.route('/predict', methods=['POST'])
def predict():
    try:
        if 'file' in request.files and request.files['file'].filename != '':
       
            file = request.files['file']
            if file and file.filename.endswith('.csv'):
                df = pd.read_csv(file)
                
          
                missing_cols = [col for col in expected_features if col not in df.columns]
                
                if missing_cols:
                    return render_template('error.html', 
                                         message=f"CSV missing {len(missing_cols)} required columns. First few missing: {missing_cols[:5]}...<br><br>Required columns in exact order: {', '.join(expected_features)}")
                
                if model_exists:
                 
                    X = df[expected_features]
                    features_scaled = scaler.transform(X)
                    predictions = model.predict(features_scaled)
                else:
              
                    energy_cols = [col for col in df.columns if 'Energy' in col]
                    if energy_cols:
                        predictions = df[energy_cols[0]] * (0.9 + np.random.random(len(df)) * 0.2)
                    else:
                        predictions = np.random.uniform(50, 200, len(df))
                
                result_df = df.copy()
                result_df['Predicted_Energy_Consumption'] = np.round(predictions, 2)
                return render_template('results.html', 
                                     tables=[result_df.to_html(classes='data', header=True, index=False)],
                                     title='Prediction Results')
            else:
                return render_template('error.html', message='Please upload a valid CSV file')
        
        else:
            
            current_time = datetime.now()
            features = create_features_from_input(request.form, current_time)
            
            if model_exists:
           
                X = pd.DataFrame([features], columns=expected_features)
                features_scaled = scaler.transform(X)
                prediction = model.predict(features_scaled)[0]
            else:
             
                base_energy = float(request.form.get('base_energy', 100.0))
                hour = int(request.form.get('hour', current_time.hour))
                occupancy = float(request.form.get('occupancy', 3.0))
              
                prediction = base_energy * (0.7 + (hour / 24) * 0.6 + (occupancy / 10) * 0.3)
            
            return render_template('results_single.html', prediction=round(prediction, 2))
    
    except Exception as e:
        return render_template('error.html', message=f"Error: {str(e)}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)