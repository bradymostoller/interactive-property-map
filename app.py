import os
import json
import time
from functools import cache

import requests
import numpy as np
import pandas as pd

import folium
from folium.plugins import MarkerCluster


from flask import Flask, render_template
TOKEN = "6d37de55-ad0b-4952-ac28-3765272b728b"

app = Flask(__name__)

df = pd.read_csv('zillow_phoenix.csv')


@app.route('/')
def index():
    # Ensure df is not reassigned inside the route
    if os.path.exists('templates/property_map.html'):
        return render_template('property_map.html')
    else:
        df_cleaned = df.dropna(subset=['longitude', 'latitude'])  # Use df_cleaned instead

        df_cleaned['rentZestimate'] = pd.to_numeric(df_cleaned['rentZestimate'], errors='coerce')
        df_cleaned['zestimate'] = pd.to_numeric(df_cleaned['zestimate'], errors='coerce')
        df_cleaned['price'] = pd.to_numeric(df_cleaned['price'], errors='coerce')

        df_cleaned['annual_rent'] = df_cleaned['rentZestimate'] * 12
        df_cleaned['gross_rental_yield'] = (df_cleaned['annual_rent'] / df_cleaned['zestimate']) * 100

        df_cleaned['gross_rental_yield'] = df_cleaned['gross_rental_yield'].replace([np.inf, -np.inf], np.nan)

        def get_marker_color(gross_yield, off_market):
            if off_market:
                return 'black'
            elif pd.isna(gross_yield):
                return 'gray'
            elif gross_yield < 5:
                return 'red'
            elif gross_yield < 8:
                return 'orange'
            else:
                return 'green'
            
        map_center = [df_cleaned['latitude'].mean(), df_cleaned['longitude'].mean()]

        m = folium.Map(location=map_center, zoom_start=12)

        marker_cluster = MarkerCluster().add_to(m)

        for idx, row in df_cleaned.iterrows():
            price = row['price']
            address = row['address']
            bedrooms = row['bedrooms']
            bathrooms = row['bathrooms']
            living_area = row['livingArea']
            gross_yield = row['gross_rental_yield']
            zestimate = row['zestimate']
            rent_zestimate = row['rentZestimate']
            property_url = row['url']
            zpid = row['zpid']

            price_formatted = f'${price:.2f}' if not pd.isna(price) else 'N/A'
            zestimate_formatted = f'${zestimate:.2f}' if not pd.isna(zestimate) else 'N/A'
            rent_zestimate_formatted = f'${rent_zestimate:.2f}' if not pd.isna(rent_zestimate) else 'N/A'
            gross_yield_formatted = f'{gross_yield:.2f}%' if not pd.isna(gross_yield) else 'N/A'

            bedrooms = int(bedrooms) if not pd.isna(bedrooms) else 'N/A'
            bathrooms = int(bathrooms) if not pd.isna(bathrooms) else 'N/A'
            living_area = int(living_area) if not pd.isna(living_area) else 'N/A'

            address_dict = json.loads(address)
            street_address = address_dict['streetAddress']

            popup_text = f"""
            <b>Address</b> {street_address} <br>
            <b>Price</b> {price_formatted} <br>
            <b>Bedrooms</b> {bedrooms} <br>
            <b>Bathrooms</b> {bathrooms} <br>
            <b>Living Area</b> {living_area} <br>
            <b>Gross Rental Yield</b> {gross_yield_formatted} <br>
            <b>Zestimate</b> {zestimate_formatted} <br>
            <b>Rent Zestimate</b> {rent_zestimate_formatted} <br>
            <a href="{property_url}" target = "_blank">Zillow Link</a><br>
            <button id = "button-{idx}" onclick="showLoadingAndRedirect({idx}, '{zpid}')">Show Price History</button>
            <div id="loading-{idx}" style="display: none;">
                <img src="https://upload.wikimedia.org/wikipedia/commons/3/3a/Gray_circles_rotate.gif" alt="loading..." width="50" height="50">

            </div>

            <script>
                function showLoadingAndRedirect(idx, zpid){{
                    document.getElementById('button-' + idx).style.display = 'none';
                    document.getElementById('loading-' + idx).style.display = 'block';
                    window.location.href = 'http://localhost:5000/price_history/' + zpid;
                }}
            </script>

            """
            color = get_marker_color(row['gross_rental_yield'], row['isOffMarket'])

            folium.Marker(
                location=[row['latitude'], row['longitude']],
                popup=folium.Popup(folium.IFrame(popup_text, width=300, height=250)),
                icon=folium.Icon(color=color, icon='home', prefix='fa')
            ).add_to(marker_cluster)

        m.save('templates/property_map.html')
        return render_template('property_map.html')

    
@app.route('/price_history/<int:zpid>')
@cache
def price_history(zpid):
    url = df[df.zpid == zpid].url.values[0]
    api_url = "https://api.brightdata.com/datasets/v3/trigger?dataset_id=gd_lxu1cz9r88uiqsosl"

    headers = {
        "Authorization": f"Bearer{TOKEN}",
        "Content-Type": 'application/json'

    }
    data = [{'url' : url}]

    response = requests.post(api_url, headers=headers, json=data)
    snapshot_id = response.json()['snapshot_id']

    time.sleep(5)

    api_url = f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}?format=csv"

    headers = headers = {
        "Authorization": f"Bearer{TOKEN}",

    }
    repsonse = requests.get(api_url, headers=headers)

    if 'Snapshot is empty' in repsonse.text:
        return 'No historic data'
    
    while 'Snapshot is not ready yet, try again in 10s' in response.text:
        time.sleep(10)
        repsonse = requests.get(api_url, headers=headers)
        if 'Snapshot is empty' in response.text:
            return 'No historic data'
        
    with open('temp.csv', 'wb') as f:
        f.write(response.content)

    price_history_df = pd.read_csv('temp.csv')
    price_history_df = price_history_df[['date', 'price']]
    price_history_df['date'] = pd.to_datetime(price_history_df['date'])
    price_history_df['date'] = price_history_df['date'].dt.strftime('%Y=%m-%d')

    return render_template('price_history.html', price_history_df=price_history_df)

if __name__ == '__main__':
    app.run(debug=True)




        
