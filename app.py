# -*- coding: utf-8 -*-
import dash
import dash_core_components as dcc
import dash_bootstrap_components as dbc
import dash_html_components as html
import dash_table
import plotly.express as px
import plotly.graph_objects as go 
from dash.dependencies import Input, Output
import os
from zipfile import ZipFile
import urllib.parse
from flask import Flask, send_from_directory

import pandas as pd
import requests
import uuid
import werkzeug

import pymzml
import numpy as np
import datashader as ds
from tqdm import tqdm

server = Flask(__name__)
app = dash.Dash(__name__, server=server, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server

df = pd.DataFrame()
df["rt"] = [1]
df["mz"] = [1]
df["i"] = [1]
cvs = ds.Canvas(plot_width=1, plot_height=1)
agg = cvs.points(df,'rt','mz', agg=ds.sum("i"))
zero_mask = agg.values == 0
agg.values = np.log10(agg.values, where=np.logical_not(zero_mask))
fig1 = px.imshow(agg, origin='lower', labels={'color':'Log10(Abundance)'}, color_continuous_scale="Hot")

NAVBAR = dbc.Navbar(
    children=[
        dbc.NavbarBrand(
            html.Img(src="https://gnps-cytoscape.ucsd.edu/static/img/GNPS_logo.png", width="120px"),
            href="https://gnps.ucsd.edu"
        ),
        dbc.Nav(
            [
                dbc.NavItem(dbc.NavLink("GNPS LCMS Dashboard", href="#")),
            ],
        navbar=True)
    ],
    color="light",
    dark=False,
    sticky="top",
)

DASHBOARD = [
    dbc.CardHeader(html.H5("GNPS LCMS Dashboard")),
    dbc.CardBody(
        [   
            dcc.Location(id='url', refresh=False),

            html.Div(id='version', children="Version - 1.0"),

            html.Br(),
            html.H3(children='GNPS USI'),
            dbc.Input(className="mb-3", id='usi', placeholder="Enter GNPS File USI"),
            html.Br(),
            dcc.Loading(
                id="download-link",
                children=[html.Div([html.Div(id="loading-output-1")])],
                type="default",
            ),
            dcc.Loading(
                id="debug-output",
                children=[html.Div([html.Div(id="loading-output-2")])],
                type="default",
            ),
            html.Br(),
            dcc.Loading(
                id="tic-plot",
                children=[html.Div([html.Div(id="loading-output-4")])],
                type="default",
            ),
            html.Br(),
            dcc.Graph(
                id='map-plot',
                figure=fig1,
                config={
                    'doubleClick': 'reset'
                }
            )
        ]
    )
]

BODY = dbc.Container(
    [
        dbc.Row([dbc.Col(dbc.Card(DASHBOARD)),], style={"marginTop": 30}),
    ],
    className="mt-12",
)

app.layout = html.Div(children=[NAVBAR, BODY])


@app.callback(Output('usi', 'value'),
              [Input('url', 'pathname')])
def determine_task(pathname):
    # Otherwise, lets use the url
    if pathname is not None and len(pathname) > 1:
        return pathname[1:]
    else:
        return "mzspec:MSV000084494:GNPS00002_A3_p:scan:1"

def create_map_fig(filename, map_selection=None):
    min_rt = 0
    max_rt = 1000000
    min_mz = 0
    max_mz = 2000

    if map_selection is not None:
        if "xaxis.range[0]" in map_selection:
            min_rt = float(map_selection["xaxis.range[0]"])
        if "xaxis.range[1]" in map_selection:
            max_rt = float(map_selection["xaxis.range[1]"])

        if "yaxis.range[0]" in map_selection:
            min_mz = float(map_selection["yaxis.range[0]"])
        if "yaxis.range[1]" in map_selection:
            max_mz = float(map_selection["yaxis.range[1]"])

    

    all_mz = []
    all_rt = []
    all_i = []
    all_scan = []
    all_index = []
    spectrum_index = 0
    number_spectra = 0

    all_ms2_mz = []
    all_ms2_rt = []

    # Understand parameters
    run = pymzml.run.Reader(filename)
    for spec in tqdm(run):
        try:
            if min_rt > spec.scan_time_in_minutes() or max_rt < spec.scan_time_in_minutes():
                continue
            # if min_rt > spectrum_index or max_rt < spectrum_index:
            #     continue
        except:
            pass
        
        if spec.ms_level == 1:
            spectrum_index += 1

            number_spectra += 1
            rt = spec.scan_time_in_minutes()

            try:
                # Filtering peaks by mz
                peaks = spec.reduce(mz_range=(min_mz, max_mz))

                # Sorting by intensity
                peaks = peaks[peaks[:,1].argsort()]
                peaks = peaks[-150:]

                mz, intensity = zip(*peaks)

                # TODO: We should filter to the top K here

                all_mz += list(mz)
                all_i += list(intensity)
                all_rt += len(mz) * [rt]
                all_scan += len(mz) * [spec.ID]
                all_index += len(mz) * [number_spectra]
            except:
                pass
        elif spec.ms_level == 2:
            try:
                ms2_mz = spec.selected_precursors[0]["mz"]
                if ms2_mz < min_mz or ms2_mz > max_mz:
                    continue
                all_ms2_mz.append(ms2_mz)
                all_ms2_rt.append(spec.scan_time_in_minutes())
            except:
                pass
            
            
    df = pd.DataFrame()
    df["mz"] = all_mz
    df["i"] = all_i
    df["rt"] = all_rt
    df["scan"] = all_scan
    df["index"] = all_index

    min_size = min(number_spectra, int(max_mz - min_mz))
    width = min(min_size*4, 500)
    height = min(int(min_size*1.75), 500)

    import time

    start = time.time()

    cvs = ds.Canvas(plot_width=width, plot_height=height)
    agg = cvs.points(df,'rt','mz', agg=ds.sum("i"))
    #agg = cvs.points(df,'index','mz', agg=ds.sum("i"))
    zero_mask = agg.values == 0
    agg.values = np.log10(agg.values, where=np.logical_not(zero_mask))
    print(time.time() - start)
    fig = px.imshow(agg, origin='lower', labels={'color':'Log10(abundance)'}, color_continuous_scale="Hot_r", width=1000, height=600)
    print(time.time() - start)
    fig.update_traces(hoverongaps=False)
    fig.update_layout(coloraxis_colorbar=dict(title='Abundance', tickprefix='1.e'), plot_bgcolor="white")
    print(time.time() - start)

    fig.update_xaxes(showline=True, linewidth=2, linecolor='black')
    fig.update_yaxes(showline=True, linewidth=2, linecolor='black')

    fig.add_trace(go.Scatter(x=all_ms2_rt, y=all_ms2_mz, mode='markers', marker=dict(color='green', size=6)))


    return fig

# Creating TIC plot
@app.callback([Output('tic-plot', 'children')],
              [Input('usi', 'value')])
def draw_tic(usi):
    usi_splits = usi.split(":")

    if "MSV" in usi_splits[1]:
        # Test: mzspec:MSV000084494:GNPS00002_A3_p:scan:1
        # Bigger Test: mzspec:MSV000083388:1_p_153001_01072015:scan:12
        lookup_url = f'https://massive.ucsd.edu/ProteoSAFe/QuerySpectrum?id={usi}'
        lookup_request = requests.get(lookup_url)

        resolution_json = lookup_request.json()

        mzML_filepath = None
        # Figuring out which file is mzML
        for resolution in resolution_json["row_data"]:
            filename = resolution["file_descriptor"]
            extension = os.path.splitext(filename)[1]

            if extension == ".mzML":
                mzML_filepath = filename
                break

        # Format into FTP link
        remote_link = f"ftp://massive.ucsd.edu/{mzML_filepath[2:]}"
    elif "GNPS" in usi_splits[1]:
        # Test: mzspec:GNPS:TASK-de188599f53c43c3aaad95491743c784-spec/spec-00000.mzML:scan:31
        filename = "-".join(usi_splits[2].split("-")[2:])
        task = usi_splits[2].split("-")[1]

        remote_link = "http://gnps.ucsd.edu/ProteoSAFe/DownloadResultFile?task={}&block=main&file={}".format(task, filename)


    # Getting Data Local, TODO: likely should serialize it
    local_filename = os.path.join("temp", werkzeug.utils.secure_filename(remote_link))
    if not os.path.isfile(local_filename):
        wget_cmd = "wget '{}' -O {}".format(remote_link, local_filename)
        os.system(wget_cmd)

    # Performing TIC Plot
    tic_trace = []
    rt_trace = []
    run = pymzml.run.Reader(local_filename)
    for n, spec in enumerate(run):
        if spec.ms_level == 1:
            rt_trace.append(spec.scan_time_in_minutes() * 60)
            tic_trace.append(sum(spec.i))

    tic_df = pd.DataFrame()
    tic_df["tic"] = tic_trace
    tic_df["rt"] = rt_trace
    fig = px.line(tic_df, x="rt", y="tic", title='TIC Plot')

    return [dcc.Graph(figure=fig)]


# Inspiration for structure from
# https://github.com/plotly/dash-datashader
# https://community.plotly.com/t/heatmap-is-slow-for-large-data-arrays/21007/2

@app.callback([Output('map-plot', 'figure'), Output('download-link', 'children')],
              [Input('usi', 'value'), Input('map-plot', 'relayoutData')])
def draw_file(usi, map_selection):
    usi_splits = usi.split(":")

    if "MSV" in usi_splits[1]:
        # Test: mzspec:MSV000084494:GNPS00002_A3_p:scan:1
        # Bigger Test: mzspec:MSV000083388:1_p_153001_01072015:scan:12
        lookup_url = f'https://massive.ucsd.edu/ProteoSAFe/QuerySpectrum?id={usi}'
        lookup_request = requests.get(lookup_url)

        resolution_json = lookup_request.json()

        mzML_filepath = None
        # Figuring out which file is mzML
        for resolution in resolution_json["row_data"]:
            filename = resolution["file_descriptor"]
            extension = os.path.splitext(filename)[1]

            if extension == ".mzML":
                mzML_filepath = filename
                break

        # Format into FTP link
        remote_link = f"ftp://massive.ucsd.edu/{mzML_filepath[2:]}"
    elif "GNPS" in usi_splits[1]:
        # Test: mzspec:GNPS:TASK-de188599f53c43c3aaad95491743c784-spec/spec-00000.mzML:scan:31
        filename = "-".join(usi_splits[2].split("-")[2:])
        task = usi_splits[2].split("-")[1]

        remote_link = "http://gnps.ucsd.edu/ProteoSAFe/DownloadResultFile?task={}&block=main&file={}".format(task, filename)


    
    # Getting Data Local, TODO: likely should serialize it
    local_filename = os.path.join("temp", werkzeug.utils.secure_filename(remote_link))
    if not os.path.isfile(local_filename):
        wget_cmd = "wget '{}' -O {}".format(remote_link, local_filename)
        os.system(wget_cmd)

    # Doing LCMS Map
    map_fig = create_map_fig(local_filename, map_selection=map_selection)

    return [map_fig, remote_link]


# @app.callback([Output('zoom-map-plot', 'figure'), Output('debug-output', 'children')],
#               [Input('usi', 'value'), Input('map-plot', 'relayoutData')])
# def draw_file(usi, map_selection):
#     usi_splits = usi.split(":")

#     if "MSV" in usi_splits[1]:
#         # Test: mzspec:MSV000084494:GNPS00002_A3_p:scan:1
#         # Bigger Test: mzspec:MSV000083388:1_p_153001_01072015:scan:12
#         lookup_url = f'https://massive.ucsd.edu/ProteoSAFe/QuerySpectrum?id={usi}'
#         lookup_request = requests.get(lookup_url)

#         resolution_json = lookup_request.json()

#         mzML_filepath = None
#         # Figuring out which file is mzML
#         for resolution in resolution_json["row_data"]:
#             filename = resolution["file_descriptor"]
#             extension = os.path.splitext(filename)[1]

#             if extension == ".mzML":
#                 mzML_filepath = filename
#                 break

#         # Format into FTP link
#         ftp_link = f"ftp://massive.ucsd.edu/{mzML_filepath[2:]}"

#         # Getting Data Local, TODO: likely should serialize it
#         local_filename = os.path.join("temp", werkzeug.utils.secure_filename(ftp_link))
        
#         # Doing LCMS Map
#         # Using this as starting code: https://community.plotly.com/t/heatmap-is-slow-for-large-data-arrays/21007/2
#         map_fig = create_map_fig(local_filename, map_selection=map_selection)

#         return [map_fig, str(map_selection)]
        

if __name__ == "__main__":
    app.run_server(debug=True, port=5000, host="0.0.0.0")
