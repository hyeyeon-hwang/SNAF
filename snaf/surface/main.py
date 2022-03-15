import pandas as pd
import numpy as np
import os,sys
import subprocess
import multiprocessing as mp
import re
import pickle
from datetime import datetime,date
from ast import literal_eval
import requests
import xmltodict
from tqdm import tqdm
from .data_io import *
from .orf_finder import *
from .orf_check import *
from .alignment import *
from .api import *




def initialize(db_dir):
    global df_exonlist
    global dict_exonCoords
    global dict_fa
    global dict_biotype
    global df_membrane_proteins
    global dict_uni_fa
    print('{} {} starting surface antigen initialization'.format(date.today(),datetime.now().strftime('%H:%M:%S')))
    transcript_db = os.path.join(db_dir,'mRNA-ExonIDs.txt')
    exon_table = os.path.join(db_dir,'Hs_Ensembl_exon_add_col.txt')
    fasta = os.path.join(db_dir,'Hs_gene-seq-2000_flank.fa')
    biotype_db = os.path.join(db_dir,'Hs_Ensembl_transcript-biotypes.txt')
    membrane_db = os.path.join(db_dir,'human_membrane_proteins.txt')
    membrane_fasta_db = os.path.join(db_dir,'uniprot_isoform_enhance.fasta')
    df_exonlist = pd.read_csv(transcript_db,sep='\t',header=None,names=['EnsGID','EnsTID','EnsPID','Exons'])  # index is number
    dict_exonCoords = exonCoords_to_dict(exon_table) 
    dict_fa = fasta_to_dict(fasta)
    dict_biotype = biotype(pd.read_csv(biotype_db,sep='\t'))  # index is number
    df_membrane_proteins = pd.read_csv(membrane_db,sep='\t',index_col=0)
    dict_uni_fa = read_uniprot_seq(membrane_fasta_db)
    print('{} {} finished surface antigen initialization'.format(date.today(),datetime.now().strftime('%H:%M:%S')))




def _run_dash_prioritizer_return_events(candidates):
    # candidates is a list of each lines, containing the newline symbol
    collect = []
    for i,line in enumerate(candidates):
        if i % 14 == 0:
            collect.append(line.rstrip('\n')[4:])
    return collect

def _run_dash_prioritizer_return_valid_indices(candidates,collect_uid,uid):
    index = collect_uid.index(uid)
    line = candidates[index*14+11]
    valid_indices = literal_eval('[' + line.rstrip('\n').split('[')[-1])
    return valid_indices



def _run_dash_prioritizer_return_sa(results,gene):
    for sa in results:
        if sa.uid == gene:
            return sa

def _run_dash_prioritizer_return_gene(candidates):
    collect = []
    for i,line in enumerate(candidates):
        if i % 14 == 12:
            collect.append(line.rstrip('\n')[12:])
    return collect


def run_dash_B_antigen(pkl,candidates,python_executable,host=None,port='8050'):
    import dash
    from dash import dcc,html,dash_table
    from dash.dependencies import Input,Output,State
    import dash_dangerously_set_inner_html
    import plotly.graph_objects as go
    with open(pkl,'rb') as f1:
        results = pickle.load(f1)   # a list of sa object
    sa, df_certain = None, None       # a binding for further nonlocal declaration 
    with open(candidates,'r') as f2:
        candidates = f2.readlines()   # a list of each lines, containing the newline symbol
    collect_uid = _run_dash_prioritizer_return_events(candidates)  # a list of all uid
    collect_gene = _run_dash_prioritizer_return_gene(candidates)   # a list of all gene symbol
    app = dash.Dash(__name__)
    app.layout = html.Div([
        html.Div([html.H2('SNAF B-antigen Viewer'),html.Br(),html.Label('Splicing Event UID: ',style={'font-weight':'bold'}),dcc.Input(id='event_selection',value=collect_uid[0],type='text',style={'width':'40%'})],style={'text-align':'center'}),
        html.Div([html.Br(),html.H2(id='exon_h2'),html.Br(),html.H2('Expression (Normal --> Tumor)'),html.Br(),dcc.Graph(id='expression')],style={'text-align':'center'}),
        html.Div([html.H2('All Exons in AltAnalyze Gene Model'),dash_table.DataTable(id='exon',columns=[{'name':column,'id':column} for column in ['subexon','chromosome','strand','start','end']],page_size=10)]),
        html.Div([html.H2('All related existing transcripts'),dash_table.DataTable(id='transcript',columns=[{'name':column,'id':column} for column in ['index','EnsGID','EnsTID','EnsPID','Exons']])]),
        html.Br(),
        html.Hr(),
        html.Div([html.H2('Transcript index'),dcc.Dropdown(id='valid_indices')],style={'text-align':'center'}),
        html.Div([html.H2('cDNA or peptide'),dcc.RadioItems(id='display',options=[
            {'label':item,'value':item} for item in ['full_length','orft','orfp','junction','score']],value='peptide')],style={'text-align':'center'}),
        html.Br(),
        html.Div([html.Button(id='submit',n_clicks=0,children='Submit',style={'width':'10%'})],style={'text-align':'center'}),
        html.Div([html.H2('Sequence'),html.Br(),html.P(id='sequence')]),
        html.Div([html.H2('Ensembl Reference'),html.Br(),html.P(id='ensembl')]),
        html.Div([html.H2('Emboss Needle Alignment (peptide)'),html.Br(),html.P(id='alignment',style={'white-space':'pre','font-family':'monospace'})]),
        html.Br(),
        html.Hr(),
        html.Div([html.H2('Downstream link'),
                  html.A(id='ensembl_link',href='http://useast.ensembl.org/Homo_sapiens/Info/Index',children='Ensembl Human'),
                  html.Br(),
                  html.A(id='Emboss_link',href='https://www.ebi.ac.uk/Tools/psa/emboss_needle/',children='Emboss Peptide Global Alignment'),
                  html.Br(),
                  html.A(id='TMHMM_link',href='https://services.healthtech.dtu.dk/service.php?TMHMM-2.0',children='TMHMM: predicting transmembrane domain'),
                  html.Br(),
                  html.A(id='SABLE_link',href='https://sable.cchmc.org/',children='SABLE: predicting solvebility and secondary structure'),
                  html.Br(),
                  html.A(id='alphafold2_link',href='https://colab.research.google.com/github/sokrypton/ColabFold/blob/main/AlphaFold2.ipynb',children='Colab version of alphafold2'),
                  html.Br(),
                  html.A(id='uniprot_link',href='https://www.uniprot.org/',children='Uniprot for protein'),
                  html.Br(),
                  html.A(id='ModFold_link',href='https://www.reading.ac.uk/bioinf/ModFOLD/',children='ModFold: 3D model assesser')])

    ])


    # function we need to define for running the app
    @app.callback(Output('expression','figure'),Output('exon_h2','children'),Output('exon','data'),Output('transcript','data'),Output('valid_indices','options'),Input('event_selection','value'))
    def select_event_show_table(value):
        nonlocal sa
        nonlocal df_certain
        sa = _run_dash_prioritizer_return_sa(results,value)  # the sa object that will be used for displaying sequence
        ensg = value.split(':')[0]        
        values = dict_exonCoords[ensg]    # {E1.1:[attrs]}
        gene_symbol = collect_gene[collect_uid.index(value)]
        coord = uid_to_coord(value)
        valid_indices = _run_dash_prioritizer_return_valid_indices(candidates,collect_uid,value)   # list of valid indices
        # data_exon
        data_exon = []
        for k,v in values.items():
            data_exon.append({'subexon':k,'chromosome':v[0],'strand':v[1],'start':v[2],'end':v[3]})
        # sort based on coordinate
        if data_exon[0]['strand'] == '+':
            data_exon.sort(reverse=False,key=lambda x:x['start'])
        elif data_exon[0]['strand'] == '-':
            data_exon.sort(reverse=True,key=lambda x:x['end'])
        # data transcript
        df_certain = df_exonlist.loc[df_exonlist['EnsGID']==ensg,:]
        df_certain = df_certain.iloc[valid_indices,:]
        df_certain.insert(loc=0,column='index',value=valid_indices)
        data_transcript = df_certain.to_dict(orient='records')
        # drop down menu
        dropdown_options = [{'label':item,'value':item} for item in valid_indices]
        # exon_h2_value
        exon_h2_value = '{} ({}) --- Coord: {}'.format(ensg,gene_symbol,coord)
        # expression plot
        expr_tumor_dict = sa.ed   # {sample:value}
        expr_tumor_dict = {sample + ',' + 'tumor': value for sample,value in expr_tumor_dict.items()}  # {sample,tumor:value}
        expr_tumor_dict = {k:v for k,v in sorted(expr_tumor_dict.items(),key=lambda x:x[1])}
        expr_gtex_df = sa.df  # index is sample name, two columns: value and tissue
        expr_gtex_dict = {row.Index + ',' + row.tissue: row.value for row in expr_gtex_df.itertuples()}   # {sample,tissue:value}
        expr_gtex_dict = {k:v for k,v in sorted(expr_gtex_dict.items(),key=lambda x:x[1])}
        node_x = []
        node_y = []
        node_text = []
        expr_gtex_dict.update(expr_tumor_dict)
        for i,(k,v) in enumerate(expr_gtex_dict.items()):
            node_x.append(i)
            node_y.append(v)
            node_text.append(k)
        node_trace = go.Scatter(x=node_x,y=node_y,mode='markers',marker={'color':'red','size':2},text=node_text,hoverinfo='text')
        fig = go.Figure(data=[node_trace],layout=go.Layout(showlegend=False))
        fig.update_xaxes(title_text='Samples(Normal -> Tumor)')
        fig.update_yaxes(title_text='Raw Read Count')
        return fig,exon_h2_value,data_exon,data_transcript,dropdown_options

    @app.callback(Output('sequence','children'),Output('ensembl','children'),Output('alignment','children'),Input('submit','n_clicks'),State('valid_indices','value'),State('display','value'),)
    def select_sequence_to_display(n_clicks,value_index,value_display):
        if value_display == 'full_length':
            sequence = sa.full_length[value_index]
            enst = df_certain.loc[df_certain['index']==value_index,:]['EnsTID'].values[0]
            ensembl_sequence = run_ensembl(ens=enst)
            emboss_alignment = 'only support peptide now'
        elif value_display == 'orft':
            sequence = sa.orft[value_index]
            enst = df_certain.loc[df_certain['index']==value_index,:]['EnsTID'].values[0]
            ensembl_sequence = run_ensembl(ens=enst)
            emboss_alignment = 'only support peptide now'
        elif value_display == 'orfp':
            sequence =  sa.orfp[value_index]
            ensp = df_certain.loc[df_certain['index']==value_index,:]['EnsPID'].values[0]
            ensembl_sequence = run_ensembl(ens=ensp)
            emboss_alignment = run_emboss(asequence=ensembl_sequence,bsequence=sequence,python_executable=python_executable)
            emboss_alignment = emboss_alignment.replace('\n','<br/>')
        elif value_display == 'junction':
            sequence = sa.junction
            enst = df_certain.loc[df_certain['index']==value_index,:]['EnsTID'].values[0]
            ensembl_sequence = run_ensembl(ens=enst)
            emboss_alignment = 'only support peptide now'
        elif value_display == 'score':
            sequence = 'Mean expression across GTEx: {} Expression frequency in cancer cohort: {}'.format(sa.score,sa.freq)
            ensp = df_certain.loc[df_certain['index']==value_index,:]['EnsPID'].values[0]
            ensembl_sequence = run_ensembl(ens=ensp)
            emboss_alignment = 'only support peptide now'
        return sequence,ensembl_sequence,dash_dangerously_set_inner_html.DangerouslySetInnerHTML(emboss_alignment)

    if host is None:
        host = subprocess.run(['hostname'],stdout=subprocess.PIPE,universal_newlines=True).stdout.split('\n')[0]
    app.run_server(host=host,port=port)
        


def uid_to_coord(uid):
    tmp_list = uid.split(':')
    if len(tmp_list) == 2:
        ensg,exons = tmp_list
    elif len(tmp_list) == 3:
        ensg = tmp_list[0]
        exons = ':'.join(tmp_list[1:])
    first,second = exons.split('-')
    # figure out start_coord
    if '_' in first:
        actual_exon,trailing = first.split('_')
        try:
            attrs = dict_exonCoords[ensg][actual_exon]
        except KeyError:
            if 'U' in actual_exon:
                proxy_exon = list(dict_exonCoords[ensg].keys())[0]
                attrs = dict_exonCoords[ensg][proxy_exon]
                chrom = attrs[0]
                strand = attrs[1]
                start_coord = trailing
            else:   # probably a rare error
                chrom = 'unknown'
                strand = 'unknown'
                start_coord = 'unknown'
        else:
            chrom = attrs[0]
            strand = attrs[1]
            start_coord = trailing
    else:
        actual_exon = first
        try:
            attrs = dict_exonCoords[ensg][actual_exon]
        except KeyError:
            chrom = 'unkonwn'
            strand = 'unknown'
            start_coord = 'unknown'
        else:
            chrom = attrs[0]
            strand = attrs[1]
            if strand == '+':
                start_coord = attrs[3]  # end
            else:
                start_coord = attrs[2]  # start
    
    # figure out end_coord
    if '_' in second:
        actual_exon,trailing = second.split('_')
        try:
            attrs = dict_exonCoords[ensg][actual_exon]
        except KeyError:
            if 'U' in actual_exon:
                end_coord = trailing
            elif 'ENSG' in actual_exon:
                end_coord = trailing
            else:
                end_coord = 'unknown'      
        else:
            end_coord = trailing
    else:
        actual_exon = second
        try:
            attrs = dict_exonCoords[ensg][actual_exon]
        except KeyError:
            if 'ENSG' in actual_exon:
                ensg_second, actual_exon_second = actual_exon.split(':')
                attrs = dict_exonCoords[ensg_second][actual_exon_second]
                if strand == '+':
                    end_coord = attrs[2]  # start
                else:
                    end_coord = attrs[3]  # end
            else:
                end_coord = 'unknown'
        else:
            if strand == '+':
                end_coord = attrs[2]  # start
            else:
                end_coord = attrs[3]  # end
    
    # assemble
    if strand == '+':
        assemble = '{}:{}-{}({})'.format(chrom,start_coord,end_coord,strand)
    else:
        assemble = '{}:{}-{}({})'.format(chrom,end_coord,start_coord,strand)

    return assemble


def split_array_to_chunks(array,cores=None):
    if not isinstance(array,list):
        raise Exception('split_array_to_chunks function works for list, not ndarray')
    array_index = np.arange(len(array))
    if cores is None:
        cores = mp.cpu_count()
    sub_indices = np.array_split(array_index,cores)
    sub_arrays = []
    for sub_index in sub_indices:
        item_in_group = []
        for i in sub_index:
            item_in_group.append(array[i])
        sub_arrays.append(item_in_group)
    return sub_arrays

def run(uids,outdir,n_stride=2,tmhmm=False,software_path=None,serialize=True):
    if not os.path.exists(outdir):
        os.mkdir(outdir)
    results = []
    for uid,score,df,ed,freq in tqdm(uids,total=len(uids)):
        sa = SurfaceAntigen(uid,score,df,ed,freq,False)
        sa.detect_type()
        sa.retrieve_junction_seq()
        sa.recovery_full_length_protein()
        sa.find_orf()
        sa.orf_check(n_stride=n_stride)
        sa.align_uniprot(tmhmm=tmhmm,software_path=software_path)
        results.append(sa)
    if serialize:
        with open(os.path.join(outdir,'surface_antigen.p'),'wb') as f:
            pickle.dump(results,f)        
    return results

def batch_run(uid_list,cores,n_stride,tmhmm=False,software_path=None,serialize=False,outdir='.',name=None):
    # currently out of active development
    sub_uid_lists = split_array_to_chunks(uid_list,cores=cores)
    pool = pool = mp.Pool(processes=cores)
    r = [pool.apply_async(func=single_run,args=(sub_uid_list,n_stride,tmhmm,software_path,serialize,)) for sub_uid_list in sub_uid_lists]
    pool.close()
    pool.join()
    results = []
    for collect in r:
        result = collect.get()
        results.extend(result)
    if name is None:
        name = 'batch_run_surface_antigen.p'
    with open(os.path.join(outdir,name),'wb') as f:
        pickle.dump(results,f)

def individual_check(uid,n_stride=2,tmhmm=False,software_path=None,exons=None,indices=[None],fragments=[None]):
    uid = uid
    sa = SurfaceAntigen(uid,0,1,False)
    get_exon_table(uid.split(':')[0])
    get_all_transcripts(uid.split(':')[0])
    get_existing_isoforms(uid.split(':')[0])
    if exons is not None:
        for exon in exons:
            print(exon,get_exon_sequence(exon,uid.split(':')[0]))
    sa.detect_type()
    sa.retrieve_junction_seq()
    sa.recovery_full_length_protein()
    sa.find_orf()
    sa.orf_check(n_stride=n_stride)
    sa.align_uniprot(tmhmm=tmhmm,software_path=software_path)
    for index,fragment in zip(indices,fragments):
        if index is None:
            continue
        else:
            sa.visualize(index=index,fragment=fragment)
    return sa

def process_est_or_long_read(gtf):
    gtf_dict = {}
    with open(gtf,'r') as f:
        transcript = -1
        for line in f:
            chrom, source, typ, start, end, score, strand, phase, attrs = line.rstrip('\n').split('\t')
            if typ == 'transcript':
                if transcript >= 0:
                    gtf_dict.setdefault(chrom,{'+':[],'-':[]})[strand].append(composition)
                transcript += 1
                composition = []                
            elif typ == 'exon':
                composition.append((start,end))
            else:
                continue
    return gtf_dict

def is_support_by_est_or_long_read(sa,op,strict=True):
    coord = uid_to_coord(sa.uid)
    start_coord, end_coord = coord.split(':')[1].split('(')[0].split('-')
    start_coord, end_coord = int(start_coord), int(end_coord)
    ensg = sa.uid.split(':')[0]
    values = dict_exonCoords[ensg]
    first_key = list(values.keys())[0]
    attrs = values[first_key]
    chrom = attrs[0]
    strand = attrs[1]
    transcripts = gtf_dict[chrom][strand]
    candidate_transcripts = []
    for transcript in transcripts:
        transcript_start = int(transcript[0][0])
        transcript_end = int(transcript[-1][-1])
        if transcript_start > start_coord:
            break
        elif transcript_start < start_coord and transcript_end > end_coord:
            candidate_transcripts.append(transcript)
        else:
            continue
    return_value = False
    return_cand = None
    for cand in candidate_transcripts:
        sequence = ''
        if strand == '+':
            for exon in cand:
                sequence += query_from_dict_fa(exon[0],exon[1],ensg,strand)
        else:
            for exon in cand[::-1]:
                sequence += query_from_dict_fa(exon[0],exon[1],ensg,strand)
        candidate_orfs = transcript2orf(sequence)
        max_orf = prioritize_orf(candidate_orfs)
        max_pep = orf2pep(max_orf)
        # junction site present
        exon_sites = []
        for exon in cand:
            exon_sites.extend([int(item) for item in exon])
        try:
            si = exon_sites.index(start_coord)
            ei = exon_sites.index(end_coord)
        except ValueError:
            continue
        if strict:
            if ei == si + 1 and max_pep == op:
                return_value = True
                return_cand = cand
                break
        else:
            if ei == si + 1:
                return_value = True
                return_cand = cand
                break
    return return_value, return_cand
    



def generate_results(pickle_path,strigency=3,outdir='.',gtf=None):
    if not os.path.exists(outdir):
        os.mkdir(outdir)
    if gtf is not None:
        global gtf_dict
        gtf_dict = process_est_or_long_read(gtf)
    with open(pickle_path,'rb') as f:
        results = pickle.load(f)
    count_candidates = 0
    count_further = 0
    candidates = []
    with open(os.path.join(outdir,'further.txt'),'w') as f2:
        for sa in results:
            valid_indices = []
            if len(sa.comments) > 0:
                print(sa,file=f2)
                count_further += 1
            else:
                send = False
                for i,(op,n,t,a) in enumerate(zip(sa.orfp,sa.nmd,sa.translatability,sa.alignment)):
                    if strigency == 5:
                        if n == '#' and t == '#' and a:
                            value,cand = is_support_by_est_or_long_read(sa,op,strict=True)
                            if value:
                                send = True
                                valid_indices.append(i)
                    elif strigency == 4:
                        if n == '#' and t == '#' and a:
                            value,cand = is_support_by_est_or_long_read(sa,op,strict=False)
                            if value:
                                send = True
                                valid_indices.append(i)
                    elif strigency == 3:
                        if n == '#' and t == '#' and a:
                            send = True
                            valid_indices.append(i)
                    elif strigency == 2:
                        if t == '#' and a:
                            send = True
                            valid_indices.append(i)
                    elif strigency == 1:
                        if a:
                            send = not send
                            valid_indices.append(i)
                if send:
                    candidates.append((sa,sa.score,sa.freq,len(valid_indices),sa.uid,valid_indices))
                    count_candidates += 1
    sorted_candidates = sorted(candidates,key=lambda x:(x[1],-x[2],-x[3]),reverse=False)
    uid_list = list(list(zip(*sorted_candidates))[4])
    ensg_list = [uid.split(':')[0] for uid in uid_list]
    gene_symbols = ensemblgene_to_symbol(ensg_list,'human')
    with open(os.path.join(outdir,'candidates.txt'),'w') as f1:
        for (sa,score,freq,hit,uid,vi),gene in zip(sorted_candidates,gene_symbols):
            print(sa,'valid_indices:{}\n'.format(vi),'gene_symbol:{}\n'.format(gene),file=f1,sep='',end='\n')
    return count_candidates,count_further


def ensemblgene_to_symbol(query,species):
    '''
    Examples::
        from sctriangulate.preprocessing import GeneConvert
        converted_list = GeneConvert.ensemblgene_to_symbol(['ENSG00000010404','ENSG00000010505'],species='human')
    '''
    # assume query is a list, will also return a list
    import mygene
    mg = mygene.MyGeneInfo()
    out = mg.querymany(query,scopes='ensemblgene',fileds='symbol',species=species,returnall=True,as_dataframe=True,df_index=True)
    result = out['out']['symbol'].fillna('unknown_gene').tolist()
    try:
        assert len(query) == len(result)
    except AssertionError:    # have duplicate results
        df = out['out']
        df_unique = df.loc[~df.index.duplicated(),:]
        result = df_unique['symbol'].fillna('unknown_gene').tolist()
    return result    
    

def get_exon_table(ensgid,outdir='.'):
    values = dict_exonCoords[ensgid]
    with open(os.path.join(outdir,'{}_exon_table.txt'.format(ensgid)),'w') as f:
        f.write('subexon\tchrom\tstrand\tstart\tend\tsuffer\n')
        for k,v in values.items():
            f.write('{}\t{}\t{}\t{}\t{}\t{}\n'.format(k,v[0],v[1],v[2],v[3],v[4]))


def get_all_transcripts(ensgid,outdir='.'):
    df_certain = df_exonlist.loc[df_exonlist['EnsGID']==ensgid,:]
    df_certain.to_csv(os.path.join(outdir,'{}_all_transcripts.txt'.format(ensgid)),sep='\t',index=None)


def get_existing_isoforms(ensgid,outdir='.'):
    with open(os.path.join(outdir,'{}_existing_isoforms.fasta'.format(ensgid)),'w') as f:
        for k,v in dict_uni_fa[ensgid].items():
            f.write('>{}\n{}\n'.format(k,v))

def get_exon_sequence(exon,ensgid):
    attrs = dict_exonCoords[ensgid][exon]
    return query_from_dict_fa(attrs[2],attrs[3],ensgid,attrs[1])

def filter_to_membrane_protein(lis):
    filtered_lis = []
    all_membrane = set(dict_uni_fa.keys())
    for uid in lis:
        ensgid = uid.split(':')[0]
        if ensgid in all_membrane:
            filtered_lis.append(uid)
    return filtered_lis



class SurfaceAntigen(object):

    def __init__(self,uid,score,df,ed,freq,check_overlap=True):
        self.uid = uid
        self.score = score
        self.df = df
        self.ed = ed
        self.freq = freq
        self.comments = []
        if check_overlap:
            if not self.is_membrane_protein():
                raise Exception('This event will not encode a surface protein')

    def is_membrane_protein(self):
        ensgid = self.uid.split(':')[0]
        if ensgid in set(df_membrane_proteins['Ens'].tolist()):
            return True
        else:
            return False

    def __str__(self):
        print_str = 'uid:{}\n'.format(self.uid)
        print_str += 'scores and freqs:{}\n'.format(','.join([str(self.score),str(self.freq)]))
        print_str += 'comments:{}\n'.format(self.comments)
        try:
            print_event_type = self.event_type
        except AttributeError:
            print_event_type = None
        print_str += 'event type:{}\n'.format(print_event_type)
        try:
            print_junction = self.junction[:5] + '...' + self.junction[-5:]
        except AttributeError:
            print_junction = None
        print_str += 'Junction:{}\n'.format(print_junction)   
        try:
            if self.full_length == ['unrecoverable']:
                print_full_length = (len(self.full_length),self.full_length)
            else:
                print_full_length = (len(self.full_length),[i for i,item in enumerate(self.full_length) if item != ''])
        except AttributeError:
            print_full_length = (None,None)
        print_str += 'Full length transcripts: length {}, indices {}\n'.format(print_full_length[0],print_full_length[1])
        try:
            if self.orft == ['unrecoverable']:
                print_orft = (len(self.orft),self.orft)
            else:
                print_orft = (len(self.orft),[i for i,item in enumerate(self.orft) if item != ''])
        except AttributeError:
            print_orft = (None,None)
        print_str += 'ORF transcripts: length {}, indices {}\n'.format(print_orft[0],print_orft[1])
        try:
            if self.orfp == ['unrecoverable']:
                print_orfp = (len(self.orfp),self.orfp)
            else:
                print_orfp = (len(self.orfp),[i for i,item in enumerate(self.orfp) if item != ''])
        except AttributeError:
            print_orfp = (None,None)
        print_str += 'ORF peptides: length {}, indices {}\n'.format(print_orfp[0],print_orfp[1])
        try:
            if self.nmd == ['unrecoverable']:
                print_nmd = (len(self.nmd),self.nmd)
            else:
                print_nmd = (len(self.nmd),[item for item in self.nmd if item != ''])
        except AttributeError:
            print_nmd =(None,None)  
        print_str += 'NMD check: length {}, indices {}\n'.format(print_nmd[0],print_nmd[1])      
        try:
            if self.translatability == ['unrecoverable']:
                print_translatability = (len(self.translatability),self.translatability)
            else:
                print_translatability = (len(self.translatability),[item for item in self.translatability if item != ''])
        except AttributeError:
            print_translatability = (None,None)
        print_str += 'tranlatability check: length {}, indices {}\n'.format(print_translatability[0],print_translatability[1])    
        try:
            if self.alignment == ['unrecoverable']:
                print_alignment = (len(self.alignment),self.alignment)
            else:
                print_alignment = (len(self.alignment),[item for item in self.alignment if item != ''])
        except AttributeError:
            print_alignment = (None,None)
        print_str += 'Alignment: length {}, indices {}\n'.format(print_alignment[0],print_alignment[1])   
        return print_str




    def detect_type(self):
        '''
        Ordinary: ENSG00000107902:E10.1-E12.1
        Alt3: ENSG00000110057:E5.1-E6.2_67996641
        Alt5: ENSG00000100321:E7.1_39364266-E8.1
        Intron Retention: ENSG00000115524:I4.1-E5.1
        Novel Exon: ENSG00000008441:I40.1_13076665-E41.1
        Trans-splicing: ENSG00000196565:E14.2-ENSG00000213934:E3.1
        UTR Event: ENSG00000164068:U0.1_49689185-E2.1
        '''
        valid_pattern = re.compile(r'^ENSG\d+:.+?-.+')
        if re.search(valid_pattern,self.uid):   # at least valid one
            if len(re.findall('ENSG',self.uid)) == 2:
                event_type = 'trans_splicing'
            elif 'U' in self.uid:
                event_type = 'utr_event'
            elif '_' in self.uid:
                subexon12 = self.uid.split(':')[1]
                subexon1, subexon2 = subexon12.split('-')
                if 'I' in subexon12:
                    event_type = 'novel_exon'
                elif '_' in subexon1 and '_' in subexon2:
                    event_type = 'alt5_alt3'
                elif '_' in subexon1 and '_' not in subexon2:
                    event_type = 'alt5'
                elif '_' in subexon2 and '_' not in subexon1:
                    event_type = 'alt3'
                else:
                    event_type = 'invalid'
            elif 'I' in self.uid:
                event_type = 'intron_retention'
            elif re.search(r'^ENSG\d+:E\d+\.\d+-E\d+\.\d+$',self.uid):
                e = self.uid.split(':')[1]
                e1 = e.split('-')[0]
                e2 = e.split('-')[1]
                e1_int = int(e1.split('.')[0][1:])
                e1_frac = int(e1.split('.')[1])
                e2_int = int(e2.split('.')[0][1:])
                e2_frac = int(e2.split('.')[1])                
                if e1 == e2:   # E5.1-E5.1
                    event_type = 'invalid'
                else:
                    if e1_int > e2_int or (e1_int==e2_int and e1_frac>e2_frac):   # E13.1-E12.4   or E12.10-E12.9
                        event_type = 'invalid'
                    else:
                        event_type = 'ordinary'
            else:
                event_type = 'invalid'
        else:
            event_type = 'invalid'
        self.event_type = event_type
        return event_type

    def retrieve_junction_seq(self):
        if self.event_type != 'invalid':
            ensid = self.uid.split(':')[0]
            subexon1,subexon2 = ':'.join(self.uid.split(':')[1:]).split('-')
            seq1 = subexon_tran(subexon1,ensid,'site1')
            seq2 = subexon_tran(subexon2,ensid,'site2')
            junction = ','.join([seq1,seq2])
            self.junction = junction
        else:
            self.junction = '$' * 10   # indicating invalid uid


    def recovery_full_length_protein(self):
        if '$' not in self.junction and '*' not in self.junction and '#' not in self.junction:
            ensgid = self.uid.split(':')[0]
            exons = ':'.join(self.uid.split(':')[1:])
            if self.event_type == 'ordinary':
                full_transcript_store,comments = recover_ordinary(ensgid,exons)
                self.comments.extend(comments)
            elif self.event_type == 'alt5' or self.event_type == 'alt3' or self.event_type == 'alt3_alt5':
                full_transcript_store,comments = recover_alt(ensgid,exons)
            else:   # novel_exon and utr_event and intron retention and trans-splicing
                full_transcript_store = ['unrecoverable']
        else:
            full_transcript_store = ['unrecoverable']
        self.full_length = full_transcript_store

    def find_orf(self):
        orft_list = []
        orfp_list = []
        for sequence in self.full_length:
            if sequence != 'unrecoverable' and sequence != '':
                if len(sequence) > 10000:
                    orft_list.append('')
                    orfp_list.append('')
                    self.comments.append('full_transcript > 10000')
                else:
                    candidate_orfs = transcript2orf(sequence)
                    max_orf = prioritize_orf(candidate_orfs)
                    max_pep = orf2pep(max_orf)
                    orft_list.append(max_orf)
                    orfp_list.append(max_pep)
            else:
                orft_list.append(sequence)
                orfp_list.append(sequence)
        self.orft = orft_list
        self.orfp = orfp_list

    def orf_check(self,n_stride):
        set_global_env(df_exonlist,dict_exonCoords,dict_fa,dict_biotype)
        nmd_check_result = nmd_check(self.uid,self.full_length,self.orft,n_stride)
        translatability_check_result = translatability_check(self.uid,self.orft)
        self.nmd = nmd_check_result
        self.translatability = translatability_check_result

    def align_uniprot(self,tmhmm,software_path=None):
        results = alignment_to_uniprot(self.orfp,self.uid,dict_uni_fa,tmhmm,software_path)
        self.alignment = results
        if tmhmm:
            subprocess.run('rm -r ./TMHMM_*',shell=True)  

    def visualize(self,index,outdir='.',name=None,fragment=None):
        full_length = self.full_length[index]
        orft = self.orft[index]
        ensgid = self.uid.split(':')[0]
        exonlist = df_exonlist.loc[df_exonlist['EnsGID']==ensgid,:]['Exons'].iloc[index].split('|')
        if full_length == '' or orft == '':
            raise Exception('please select index that are not empty based on SurfaceAntigen summary')
        else:
            import matplotlib.pyplot as plt
            from matplotlib.patches import Rectangle,Patch
            l = len(full_length)
            start_o = full_length.index(orft)
            end_o = start_o + (len(orft)-1)
            fig,ax = plt.subplots()
            ax.set_xlim(-0.05,1.05)
            ax.set_ylim(-0.05,1.05)
            # draw full_length
            rect_full_length = Rectangle((0,0.8),1,0.1,linewidth=0.5,facecolor='g',edgecolor='k')
            ax.add_patch(rect_full_length)
            # draw orft
            rect_orft = Rectangle((start_o/l,0.6),(end_o-start_o)/l,0.1,linewidth=0.5,facecolor='orange',edgecolor='k')
            ax.add_patch(rect_orft)
            # draw junction            
            junction = ''.join([self.junction.split(',')[0][1:],self.junction.split(',')[1][:-1]])
            start_j = full_length.index(junction)
            end_j = start_j + (len(junction)-1)
            rect_junction = Rectangle((start_j/l,0.4),(end_j-start_j)/l,0.1,linewidth=0.5,facecolor='r',edgecolor='k')
            ax.add_patch(rect_junction)
            # draw exonlist
            for i,exon in enumerate(exonlist):
                attrs = dict_exonCoords[ensgid][exon]
                seq = query_from_dict_fa(int(attrs[2])+1,int(attrs[3])-1,ensgid,attrs[1])
                try:
                    start_s = full_length.index(seq)
                except ValueError:   # say E9.2-E13.1 is the novel splicing event, skip the E11.1 in the list, so E11.1 won't align
                    continue 
                end_s = start_s + (len(seq)-1)
                if i % 2 == 0:
                    rect_seq = Rectangle((start_s/l,0.2),(end_s-start_s)/l,0.1,linewidth=0.1,facecolor='pink',edgecolor='k')
                else:
                    rect_seq = Rectangle((start_s/l,0.2),(end_s-start_s)/l,0.1,linewidth=0.1,facecolor='b',edgecolor='k')
                ax.add_patch(rect_seq)
                ax.text(x=(start_s + end_s)/2/l,y=0.3,s=exon,rotation=90,fontsize=2,va='bottom')
            # draw fragment
            if fragment is not None:
                start_f = full_length.index(fragment)
                end_f = start_f + (len(fragment)-1)
                rect_fragment = Rectangle((start_f/l,0.0),(end_f-start_f)/l,0.1,linewidth=0.5,facecolor='magenta',edgecolor='k')
                ax.add_patch(rect_fragment)
            # draw legend
            ax.legend(handles=[Patch(color=i) for i in ['g','orange','r','magenta']],labels=['transcript','ORF','junction','fragment'],
                      bbox_to_anchor=(1,1),loc='upper left',frameon=False)
            # draw title
            ax.set_title('{}_{}'.format(self.uid,index))
            if name is None:
                name = '{}_{}.pdf'.format(self.uid.replace(':','_'),index)
            plt.savefig(os.path.join(outdir,name),bbox_inches='tight')
            plt.close()

        


    


    
# standalone functions
def subexon_tran(subexon,EnsID,flag):  # flag either site1 or site2
    '''
    1. subexon can take multiple forms depending on the event type
    E1.2 or I3.4
    E6.2_67996641 or I40.1_13076665, also depending on whether they are subexon1 or subexon2
    ENSG00000213934:E3.1 or ENSG00000213934:E2.1_473843893894
    U0.1_49689185
    2. everything with trailing suffix will depend on the subexon1 or subexon2, but sometimes, it is fixed (trans-splicing can only be in subexon2)
    3. to be clear, the exon_seq returned is always 5'-3' sequence, not forward anymore.
    '''
    try:   # E1.2 or I3.4
        attrs = dict_exonCoords[EnsID][subexon]  # [chr,strand,start,end,suffer] 
        exon_seq = query_from_dict_fa(attrs[2],attrs[3],EnsID,attrs[1])  
    except KeyError:
        if ':' in subexon: # ENSG00000213934:E3.1
            fusionGeneEnsID = subexon.split(':')[0] 
            fusionGeneExon = subexon.split(':')[1]        
            if  '_' in fusionGeneExon:   # ENSG:E2.1_473843893894
                suffix = fusionGeneExon.split('_')[1]
                subexon = fusionGeneExon.split('_')[0]
                attrs = dict_exonCoords[fusionGeneEnsID][subexon]
                if attrs[1] == '+':  
                    exon_seq = query_from_dict_fa(suffix,attrs[3],fusionGeneEnsID,attrs[1]) 
                else:  
                    exon_seq = query_from_dict_fa(attrs[2],suffix,fusionGeneEnsID,attrs[1])
            else:  # ENSG:E2.1
                try:
                    attrs = dict_exonCoords[fusionGeneEnsID][fusionGeneExon]
                except KeyError:
                    exon_seq = '*' * 10  # indicator for error on MultiPath-PSI itself
                else:
                    exon_seq = query_from_dict_fa(attrs[2],attrs[3],fusionGeneEnsID,attrs[1]) 

        else:  # could be trailing or utr, or non-existing ordinary subexon
            try:
                suffix = subexon.split('_')[1]
            except IndexError: # the logic is there's a subexon E45.3, it is no trailing, but just not in the exonCoords.
                exon_seq = '*' * 10  # indicator for error on MultiPath-PSI itself
            else:
                subexon = subexon.split('_')[0]
                try:
                    attrs = dict_exonCoords[EnsID][subexon]
                except KeyError:  # must be UTR
                    chrUTR,strandUTR = utrAttrs(EnsID) # this is get from a random subexon under that EnsID
                    exon_seq = utrJunction(suffix,EnsID,strandUTR,chrUTR,flag)  
                else:   # must be trailing
                    if flag == 'site2':
                        if attrs[1] == '+':  
                            exon_seq = query_from_dict_fa(suffix,attrs[3],EnsID,attrs[1]) 
                        else:  
                            exon_seq = query_from_dict_fa(attrs[2],suffix,EnsID,attrs[1])
                    elif flag == 'site1':  # not affected by overhang since it is site1
                        if attrs[1] == '+': 
                            exon_seq = query_from_dict_fa(attrs[2],suffix,EnsID,attrs[1])
                        else:
                            exon_seq = query_from_dict_fa(suffix,attrs[3],EnsID,attrs[1])
    return exon_seq

def retrieveSeqFromUCSCapi(chr_,start,end):
    url = 'http://genome.ucsc.edu/cgi-bin/das/hg38/dna?segment={0}:{1},{2}'.format(chr_,start,end)
    response = requests.get(url)
    status_code = response.status_code
    assert status_code == 200
    try:
        my_dict = xmltodict.parse(response.content)
    except:
        exon_seq = '#' * 10  # indicating the UCSC doesn't work
        return exon_seq
    exon_seq = my_dict['DASDNA']['SEQUENCE']['DNA']['#text'].replace('\n','').upper()
    return exon_seq

def utrAttrs(EnsID):  # try to get U0.1's attribute, but dict_exonCoords doesn't have, so we just wanna get the first entry for its EnsGID
    exonDict = dict_exonCoords[EnsID] 
    attrs = next(iter(exonDict.values()))
    chr_,strand = attrs[0],attrs[1]
    return chr_,strand

def utrJunction(site,EnsGID,strand,chr_,flag,seq_len=100):  # U0.1_438493849, here 438493849 means the site (suffix)
    if flag == 'site1' and strand == '+':  # U0.1_438493849 - E2.2
        otherSite = int(site) - seq_len + 1   # extract UTR with length = 100
        exon_seq = retrieveSeqFromUCSCapi(chr_,int(otherSite),int(site))
    elif flag == 'site1' and strand == '-':    
        otherSite = int(site) + seq_len - 1 
        exon_seq = retrieveSeqFromUCSCapi(chr_,int(site),int(otherSite))
        exon_seq = str(Seq(exon_seq).reverse_complement())
    elif flag == 'site2' and strand == '+':  # E5.3 - U5.4_48374838
        otherSite = int(site) + seq_len -1
        exon_seq = retrieveSeqFromUCSCapi(chr_,int(site),int(otherSite))
    elif flag == 'site2' and strand == '-':
        otherSite = int(site) - seq_len + 1
        exon_seq = retrieveSeqFromUCSCapi(chr_,int(otherSite),int(site))
        exon_seq = str(Seq(exon_seq).reverse_complement())
    return exon_seq

def query_from_dict_fa(abs_start,abs_end,EnsID,strand):
    '''
    abs_start and abs_end always means the xth base in forward strand
    the returned exon_seq, however, means the 5'-3' seq depending on the strand information.
    '''
    if strand == '+':        
        start = int(dict_fa[EnsID][1])
        end = int(dict_fa[EnsID][2])
        seq = dict_fa[EnsID][3]
        start_index = int(abs_start) - start + 2000
        end_index = int(abs_end) - start + 1 + 2000
        exon_seq = seq[start_index:end_index]
    
    elif strand == '-':
        start = int(dict_fa[EnsID][1])
        end = int(dict_fa[EnsID][2])
        seq_reverse = dict_fa[EnsID][3]
        seq_forward = str(Seq(seq_reverse).reverse_complement())  # Hs_gene.fa restore the reverse strand info
        start_index = int(abs_start) - start + 2000
        end_index = int(abs_end) - start + 1 + 2000 # endpoint in python is non-inclusive
        exon_seq_1 = seq_forward[start_index:end_index]
        s = Seq(exon_seq_1)
        exon_seq = str(s.reverse_complement())
    return exon_seq


def recover_alt(ensgid,exons):
    # exons is E4.1_888888-E5.6 or E4.1-E5.6_888888 or E4.1_888888-E5.6_8888888
    # match E4.1 and E5.6 separately, and incorporate the trailing coordinates while pasting the sequence
    # if you want to debug, just print out each exon right after pointer_down
    comments = []
    e1,e2 = exons.split('-')
    # for e1
    if '_' not in e1:
        e1_exon, e1_trailing = e1,None
    else:
        e1_exon, e1_trailing = e1.split('_')
    # for e2
    if '_' not in e2:
        e2_exon, e2_trailing = e2,None
    else:
        e2_exon, e2_trailing = e2.split('_')    
    strand = dict_exonCoords[ensgid][e1_exon][1]
    full_transcript_store = []  # ['',full_transcript1_seq,...] 
    df_certain = df_exonlist.loc[df_exonlist['EnsGID']==ensgid,:]
    pattern1_1 = re.compile(r'{}\|'.format(e1_exon))
    pattern2_1 = re.compile(r'{}\|'.format(e2_exon))
    pattern2_2 = re.compile(r'{}$'.format(e2_exon))
    for i,item in enumerate(df_certain['Exons']):
        match1 = re.search(pattern1_1,item)
        match2 = re.search(pattern2_1,item) or re.search(pattern2_2,item)
        condition = match1 and match2
        if condition:
            if match1.start() >= match2.start():    # E16.2|E16.3|E23.1|E35.10|E35.11|E36.1|E37.1|E38.1|E39.1|E40.1|E41.1|E42.2|E43.1|E43.2|E43.4|E43.5|E2.4|E5.1|E5.2|E5.3|E5.4|E5.5 
                full_transcript_store.append('')
                comments.append('wonky ordered database')
            else:
                full_transcript = ''
                exonlist = iter(item.split('|'))
                l_exon = next(exonlist,'end')
                l_exon_int = int(l_exon.split('.')[0][1:])
                l_exon_frac = int(l_exon.split('.')[1])
                pointer_up = dict_exonCoords[ensgid][l_exon][2] if strand == '+' else dict_exonCoords[ensgid][l_exon][3]
                while True:
                    n_exon = next(exonlist,'end')
                    if n_exon == 'end':
                        pointer_down = dict_exonCoords[ensgid][l_exon][3] if strand == '+' else dict_exonCoords[ensgid][l_exon][2]
                        frag_seq = query_from_dict_fa(pointer_up,pointer_down,ensgid,strand) if strand == '+' else query_from_dict_fa(pointer_down,pointer_up,ensgid,strand)
                        full_transcript += frag_seq
                        break
                    if n_exon == e1_exon:
                        n_exon_int = int(n_exon.split('.')[0][1:])
                        n_exon_frac = int(n_exon.split('.')[1])
                        if n_exon_int > l_exon_int or (n_exon_int == l_exon_int and n_exon_frac > l_exon_frac + 1):
                            # solve the one before the e1
                            pointer_down = dict_exonCoords[ensgid][l_exon][3] if strand == '+' else dict_exonCoords[ensgid][l_exon][2]
                            frag_seq = query_from_dict_fa(pointer_up,pointer_down,ensgid,strand) if strand == '+' else query_from_dict_fa(pointer_down,pointer_up,ensgid,strand)
                            full_transcript += frag_seq
                            pointer_up = dict_exonCoords[ensgid][n_exon][2] if strand == '+' else dict_exonCoords[ensgid][n_exon][3]
                            # now solve e1 itself
                            if e1_trailing is None:
                                pointer_down = dict_exonCoords[ensgid][n_exon][3] if strand == '+' else dict_exonCoords[ensgid][n_exon][2]
                            else:
                                pointer_down = e1_trailing
                            frag_seq = query_from_dict_fa(pointer_up,pointer_down,ensgid,strand) if strand == '+' else query_from_dict_fa(pointer_down,pointer_up,ensgid,strand)
                            full_transcript += frag_seq
                        else:   # E3.4|E3.5|E4.1|E4.2|E5.1|E5.2|E6.1|E6.2, e1 is E5.2, e2 is E6.2
                            # solve the one before e1 and e1 together
                            if e1_trailing is None:
                                pointer_down = dict_exonCoords[ensgid][n_exon][3] if strand == '+' else dict_exonCoords[ensgid][n_exon][2]
                            else:
                                pointer_down = e1_trailing
                            frag_seq = query_from_dict_fa(pointer_up,pointer_down,ensgid,strand) if strand == '+' else query_from_dict_fa(pointer_down,pointer_up,ensgid,strand)
                            full_transcript += frag_seq
                        while True:   # skip till e2
                            n_exon = next(exonlist,'end')
                            if n_exon == e2_exon:
                                l_exon = n_exon
                                l_exon_int = int(l_exon.split('.')[0][1:])
                                l_exon_frac = int(l_exon.split('.')[1])
                                if e2_trailing is None:
                                    pointer_up = dict_exonCoords[ensgid][l_exon][2] if strand == '+' else dict_exonCoords[ensgid][l_exon][3]
                                else:
                                    pointer_up = e2_trailing
                                break
                        continue
                    else:
                        n_exon_int = int(n_exon.split('.')[0][1:])
                        n_exon_frac = int(n_exon.split('.')[1])
                        if n_exon_int > l_exon_int or (n_exon_int == l_exon_int and n_exon_frac > l_exon_frac + 1):
                            pointer_down = dict_exonCoords[ensgid][l_exon][3] if strand == '+' else dict_exonCoords[ensgid][l_exon][2]
                            frag_seq = query_from_dict_fa(pointer_up,pointer_down,ensgid,strand) if strand == '+' else query_from_dict_fa(pointer_down,pointer_up,ensgid,strand)
                            full_transcript += frag_seq
                            pointer_up = dict_exonCoords[ensgid][n_exon][2] if strand == '+' else dict_exonCoords[ensgid][n_exon][3]
                            l_exon = n_exon
                            l_exon_int = n_exon_int
                            l_exon_frac = n_exon_frac                        
                        else:
                            l_exon = n_exon
                            l_exon_frac = n_exon_frac
                full_transcript_store.append(full_transcript)
        else:
            full_transcript_store.append('')

    return full_transcript_store,comments    


def recover_ordinary(ensgid,exons,must_novel=True):
    # exons is E4.1-E5.6
    # match E4.1 and E5.6 separately
    # if you want to debug, just print out each exon right after pointer_down
    comments = []
    e1,e2 = exons.split('-')
    strand = dict_exonCoords[ensgid][e1][1]
    full_transcript_store = []  # ['',full_transcript1_seq,...] 
    df_certain = df_exonlist.loc[df_exonlist['EnsGID']==ensgid,:]
    pattern1_1 = re.compile(r'{}\|'.format(e1))
    pattern2_1 = re.compile(r'{}\|'.format(e2))
    pattern2_2 = re.compile(r'{}$'.format(e2))
    pattern3_1 = re.compile(r'{}\|{}\|'.format(e1,e2))
    pattern3_2 = re.compile(r'{}\|{}$'.format(e1,e2))
    for i,item in enumerate(df_certain['Exons']):
        match1 = re.search(pattern1_1,item)
        match2 = re.search(pattern2_1,item) or re.search(pattern2_2,item)
        match3 = re.search(pattern3_1,item) or re.search(pattern3_2,item)
        if must_novel:
            condition = (match1 and match2) and (not match3)
        else:
            condition = match1 and match2
        if condition:
            if match1.start() >= match2.start():    # E16.2|E16.3|E23.1|E35.10|E35.11|E36.1|E37.1|E38.1|E39.1|E40.1|E41.1|E42.2|E43.1|E43.2|E43.4|E43.5|E2.4|E5.1|E5.2|E5.3|E5.4|E5.5 
                full_transcript_store.append('')
                comments.append('wonky ordered database')
            else:
                full_transcript = ''
                exonlist = iter(item.split('|'))
                l_exon = next(exonlist,'end')
                l_exon_int = int(l_exon.split('.')[0][1:])
                l_exon_frac = int(l_exon.split('.')[1])
                pointer_up = dict_exonCoords[ensgid][l_exon][2] if strand == '+' else dict_exonCoords[ensgid][l_exon][3]
                while True:
                    n_exon = next(exonlist,'end')
                    if n_exon == 'end':
                        pointer_down = dict_exonCoords[ensgid][l_exon][3] if strand == '+' else dict_exonCoords[ensgid][l_exon][2]
                        frag_seq = query_from_dict_fa(pointer_up,pointer_down,ensgid,strand) if strand == '+' else query_from_dict_fa(pointer_down,pointer_up,ensgid,strand)
                        full_transcript += frag_seq
                        break
                    if n_exon == e1:
                        n_exon_int = int(n_exon.split('.')[0][1:])
                        n_exon_frac = int(n_exon.split('.')[1])
                        if n_exon_int > l_exon_int or (n_exon_int == l_exon_int and n_exon_frac > l_exon_frac + 1):
                            # solve the one before the e1
                            pointer_down = dict_exonCoords[ensgid][l_exon][3] if strand == '+' else dict_exonCoords[ensgid][l_exon][2]
                            frag_seq = query_from_dict_fa(pointer_up,pointer_down,ensgid,strand) if strand == '+' else query_from_dict_fa(pointer_down,pointer_up,ensgid,strand)
                            full_transcript += frag_seq
                            pointer_up = dict_exonCoords[ensgid][n_exon][2] if strand == '+' else dict_exonCoords[ensgid][n_exon][3]
                            # now solve e1 itself
                            pointer_down = dict_exonCoords[ensgid][n_exon][3] if strand == '+' else dict_exonCoords[ensgid][n_exon][2]
                            frag_seq = query_from_dict_fa(pointer_up,pointer_down,ensgid,strand) if strand == '+' else query_from_dict_fa(pointer_down,pointer_up,ensgid,strand)
                            full_transcript += frag_seq
                        else:   # E3.4|E3.5|E4.1|E4.2|E5.1|E5.2|E6.1|E6.2, e1 is E5.2, e2 is E6.2
                            # solve the one before e1 and e1 together
                            pointer_down = dict_exonCoords[ensgid][n_exon][3] if strand == '+' else dict_exonCoords[ensgid][n_exon][2]
                            frag_seq = query_from_dict_fa(pointer_up,pointer_down,ensgid,strand) if strand == '+' else query_from_dict_fa(pointer_down,pointer_up,ensgid,strand)
                            full_transcript += frag_seq
                        while True:   # skip till e2
                            n_exon = next(exonlist,'end')
                            if n_exon == e2:
                                l_exon = n_exon
                                l_exon_int = int(l_exon.split('.')[0][1:])
                                l_exon_frac = int(l_exon.split('.')[1])
                                pointer_up = dict_exonCoords[ensgid][l_exon][2] if strand == '+' else dict_exonCoords[ensgid][l_exon][3]
                                break
                        continue
                    else:
                        n_exon_int = int(n_exon.split('.')[0][1:])
                        n_exon_frac = int(n_exon.split('.')[1])
                        if n_exon_int > l_exon_int or (n_exon_int == l_exon_int and n_exon_frac > l_exon_frac + 1):
                            pointer_down = dict_exonCoords[ensgid][l_exon][3] if strand == '+' else dict_exonCoords[ensgid][l_exon][2]
                            frag_seq = query_from_dict_fa(pointer_up,pointer_down,ensgid,strand) if strand == '+' else query_from_dict_fa(pointer_down,pointer_up,ensgid,strand)
                            full_transcript += frag_seq
                            pointer_up = dict_exonCoords[ensgid][n_exon][2] if strand == '+' else dict_exonCoords[ensgid][n_exon][3]
                            l_exon = n_exon
                            l_exon_int = n_exon_int
                            l_exon_frac = n_exon_frac                        
                        else:
                            l_exon = n_exon
                            l_exon_frac = n_exon_frac
                full_transcript_store.append(full_transcript)
        else:
            full_transcript_store.append('')

    return full_transcript_store,comments