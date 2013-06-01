import compare_data
import cPickle as pickle
import uuid, os
import td_config
import td_parsers
import td_persist
import reverseproxied

from flask import Flask
from flask import render_template
from flask import request
from flask import url_for
from flask import redirect
from flask import Markup
import flask
from werkzeug import secure_filename


app = Flask(__name__)
app.wsgi_app = reverseproxied.ReverseProxied(app.wsgi_app)


@app.route('/')
def index():
    return copy_paste_compare()

@app.route('/copy-paste-compare', methods=['GET', 'POST'])
@app.route('/tables_input', methods=['GET', 'POST'])
def copy_paste_compare():
    if request.method == 'GET':
        return render_template('new_tables_input.html',
                               header_tab_classes={'copy-paste-compare': 'active'})

    table1 = td_parsers.load_table_from_handson_json(request.json['dataTable1'])
    table2 = td_parsers.load_table_from_handson_json(request.json['dataTable2'])
    diffs, sames = compare_data.compare_td_tables(table1, table2, None)

    results_id = td_persist.store_results(table1, table2, diffs, sames)

    redirect_url = url_for('show_results', results_id=results_id)
    return flask.jsonify(redirect_url=redirect_url)

@app.route('/file-compare', methods=['GET', 'POST'])
def file_compare():
    if request.method == 'GET':
        return render_template('file_compare.html',
                               header_tab_classes={'file-compare': 'active'})

    actual_results_file = request.files['actual_results']
    expected_results_file = request.files['expected_results']
    for results_file in (actual_results_file, expected_results_file):
        if results_file and allowed_file(results_file.filename):
            filename = secure_filename(results_file.filename)
            results_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return redirect(url_for('file_compare'))

@app.route('/xls-worksheet-compare', methods=['GET', 'POST'])
def xls_worksheet_compare():
    if request.method == 'GET':
        return render_template('xls_worksheet_compare.html',
                               header_tab_classes={'xls-worksheet-compare': 'active'})

    worksheet_results_file = request.files['worksheet_file']
    if worksheet_results_file and allowed_file(worksheet_results_file.filename):
        filename = secure_filename(worksheet_results_file.filename)
        file_location = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        worksheet_results_file.save(file_location)

        expected_worksheet_name = "Reference"
        actual_worksheet_name = "Actual"

        expected_results_table = td_parsers.load_table_from_xls(file_location, expected_worksheet_name)
        actual_results_table = td_parsers.load_table_from_xls(file_location, actual_worksheet_name)

        # diffs, sames = compare_data.compare_td_tables(expected_results_table, actual_results_table, None)
        # results_id = td_persist.store_results(expected_results_table, actual_results_table, diffs, sames)

        comparison = compare_data.new_compare_td_tables(expected_results_table, actual_results_table, None)
        comparison_id = td_persist.store_new_comparison(comparison)


        redirect_url = url_for('show_new_results', comparison_id=comparison_id)
        return redirect(redirect_url)

    return redirect(url_for('xls_worksheet_compare'))

@app.route('/compare', methods=['GET', 'POST'])
def compare():
    if request.method == 'GET':
        return render_template('full_compare.html',
                               header_tab_classes={'table-compare': 'active'})

@app.route('/manage-tables', methods=['GET', 'POST'])
def manage_tables():
    if request.method == 'GET':
        return render_template('manage-tables.html',
                               header_tab_classes={'manage-tables': 'active'})

@app.route('/results/<results_id>', methods=['GET'])
def show_results(results_id):
    options = td_config.RenderTableOptions()

    results = td_persist.retrieve_results(results_id)
    t1_row_count = results["t1_info"]["row_count"]
    t2_row_count = results["t2_info"]["row_count"]
    if t1_row_count != t2_row_count:
        return "Error - different numbers of rows (%s / %s)" % (t1_row_count,
                                                                t2_row_count)

    t1_col_count = results["t1_info"]["col_count"]
    t2_col_count = results["t2_info"]["col_count"]
    if t1_col_count != t2_col_count:
        return "Error - different numbers of columns (%s / %s)" % (t1_col_count,

                                                                   t2_col_count)

    table_rows = []
    for row_index in range(t1_row_count):
        table_row = []
        for col_index in range(t1_col_count):
            if (row_index, col_index) in results["sames"]:
                item = ("%s" % results["sames"][(row_index, col_index)], "ok")
            else:
                item = (Markup("Expected: %s<br>Actual: %s" %
                               results["diffs"][(row_index, col_index)]),
                        "mismatch")

            table_row.append(item)

        table_rows.append(table_row)

    return render_template('data_comparison_results_handson.html',
                           table_rows=table_rows,
                           options=options,
                           header_tab_classes={})

@app.route('/new_results/<comparison_id>', methods=['GET'])
def show_new_results(comparison_id):
    options = td_config.RenderTableOptions()

    report_notes = []

    comparison = td_persist.retrieve_new_comparison(comparison_id)
    expected_row_count = comparison.expected_table.row_count
    actual_row_count = comparison.actual_table.row_count
    # actual_row_count = results["t2_info"]["row_count"]
    if expected_row_count != actual_row_count:
        report_note = "Error - different numbers of rows (%s / %s)" % (expected_row_count,
                                                                       actual_row_count)
        report_notes.append(report_note)

    expected_col_count = comparison.expected_table.col_count
    actual_col_count = comparison.actual_table.col_count
    if expected_col_count != actual_col_count:
        report_note = "Error - different numbers of columns (%s / %s)" % (expected_col_count,
                                                                          actual_col_count)
        report_notes.append(report_note)

    table_rows = []
    for row_index in range(comparison.max_rows):
        table_row = []
        for col_index in range(comparison.max_cols):
            if (row_index, col_index) in comparison.same_cells:
                item = ("%s" % comparison.same_cells[(row_index, col_index)], "ok")
            elif (row_index, col_index) in comparison.diff_cells:
                item = (Markup("Expected: %s<br>Actual: %s" %
                               comparison.diff_cells[(row_index, col_index)]),
                        "mismatch")
            elif (row_index, col_index) in comparison.expected_table_only_cells:
                item = (Markup("Expected: %s<br>Actual: --missing--" %
                               comparison.expected_table_only_cells[(row_index, col_index)]),
                        "missing_expected")
            elif (row_index, col_index) in comparison.actual_table_only_cells:
                item = (Markup("Expected: --missing--<br>Actual: %s" %
                               comparison.actual_table_only_cells[(row_index, col_index)]),
                        "missing_actual")
            elif (row_index, col_index) in comparison.neither_table_cell_coords:
                item = ("", "padding")
            else:
                raise Exception("Untreated cell: %s" % ((row_index, col_index)))


            table_row.append(item)

        table_rows.append(table_row)

    return render_template('data_comparison_new_results.html',
                           table_rows=table_rows,
                           options=options,
                           header_tab_classes={})

ALLOWED_EXTENSIONS = set(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'xls', 'csv'])

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

@app.route('/uploads', methods=['GET', 'POST'])
def uploads():
    if request.method == 'POST':
        file1 = request.files['file1']
        if file1 and allowed_file(file1.filename):
            filename = secure_filename(file1.filename)
            file1.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            return redirect(url_for('uploaded_file',
                                    filename=filename))
    return render_template("uploads.html")

from flask import send_from_directory

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'],
                               filename)

UPLOAD_FOLDER = '/tmp'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if __name__ == "__main__":
    app.run(host='0.0.0.0',
            debug=True)
