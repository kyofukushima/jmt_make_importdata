import streamlit as st
import pandas as pd
import numpy as np
import io
import csv
import base64
from typing import List, Dict, Any, Optional
import chardet
from datetime import datetime
import os

st.set_page_config(page_title="ジモトクデータ処理アプリ", layout="wide")

# データ型のマッピング
DATA_TYPE_MAPPING = {
    "string": str,
    "number": np.float64,
    "boolean": bool,
    "object": object,
    "array": object
}

def detect_encoding(file_path):
    """
    ファイルのエンコーディングを検出
    """
    with open(file_path, 'rb') as f:
        raw_data = f.read()
        result = chardet.detect(raw_data)
        return result['encoding']

def insert_data_types(df: pd.DataFrame) -> pd.DataFrame:
    """
    データ項目一覧に基づいて、1行目として各列のデータ型を挿入
    """
    # データ項目一覧からデータ型情報を取得
    data_types_row = {}
    
    try:
        # エンコーディングを自動検出
        encoding = detect_encoding("データ項目一覧.md")
        
        # データ項目一覧.mdからデータを読み込む
        with open("データ項目一覧.md", "r", encoding=encoding) as f:
            lines = f.readlines()
        
        # ヘッダー行を除外
        data_lines = [line for line in lines if line.startswith("|") and not line.startswith("|項目|") and not line.startswith("|--")]
        
        # 各行からデータ型情報を抽出
        for line in data_lines:
            columns = line.strip().split("|")
            if len(columns) >= 4:
                item_name = columns[2].strip()
                data_type = columns[3].strip()
                if item_name and data_type in DATA_TYPE_MAPPING:
                    data_types_row[item_name] = data_type
    except Exception as e:
        st.warning(f"データ項目一覧.mdの読み込み中にエラーが発生しました: {e}")
        st.info("デフォルトのデータ型情報を使用します")
    
    # 新しい行を挿入するためのデータを作成
    data_type_values = {}
    
    for col in df.columns:
        if col in data_types_row:
            data_type_values[col] = data_types_row[col]
        else:
            data_type_values[col] = "string"  # デフォルトはstring
    
    # 1行目にデータ型行を挿入
    new_df = pd.concat([
        pd.DataFrame([data_type_values]),  # データ型行を最初に
        df  # 元のデータフレーム全体
    ]).reset_index(drop=True)
    
    return new_df

def get_csv_download_link(df: pd.DataFrame, encoding: str = 'utf-8', add_bom: bool = True) -> str:
    """
    データフレームをCSVとしてダウンロードするためのリンクを生成
    
    Parameters:
    -----------
    df : pd.DataFrame
        ダウンロードするデータフレーム
    encoding : str
        エンコーディング（'utf-8'または'shift_jis'）
    add_bom : bool
        BOMを付けるかどうか（UTF-8の場合のみ有効）
    
    Returns:
    --------
    str
        ダウンロードリンク
    """
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False, quoting=csv.QUOTE_ALL, encoding=encoding)
    csv_str = csv_buffer.getvalue()
    
    # バイトに変換
    csv_bytes = csv_str.encode(encoding)
    
    # BOMの追加（UTF-8の場合のみ）
    if encoding == 'utf-8' and add_bom:
        csv_bytes = b'\xef\xbb\xbf' + csv_bytes
    
    b64 = base64.b64encode(csv_bytes).decode()
    
    # Content-Type設定
    content_type = f'text/csv;charset={encoding}'
    
    href = f'data:{content_type};base64,{b64}'
    return href

def main():
    st.title("ジモトクデータ処理アプリ")
    
    # セッション状態の初期化
    if "original_filename" not in st.session_state:
        st.session_state.original_filename = ""
    
    uploaded_file = st.file_uploader("エクセルまたはCSVファイルをアップロード", type=["xlsx", "csv"])
    
    if uploaded_file is not None:
        try:
            # 元のファイル名を保存
            original_filename = uploaded_file.name
            # 拡張子を除いたファイル名を保存
            st.session_state.original_filename = os.path.splitext(original_filename)[0]
            
            # ファイル読み込み
            if uploaded_file.name.endswith('.csv'):
                try:
                    df = pd.read_csv(uploaded_file)
                except UnicodeDecodeError:
                    # エンコーディングエラーが発生した場合、cp932（Shift-JIS）で再試行
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file, encoding='cp932')
            else:
                df = pd.read_excel(uploaded_file)
            
            st.success(f"ファイル '{original_filename}' の読み込みが完了しました")
            
            # 元データの表示とデータの行数表示
            st.subheader("元データ")
            
            # データの行数を表示
            num_rows = len(df)
            st.info(f"データの行数: {num_rows}行")
            
            with st.expander("元のデータを表示"):
                st.dataframe(df)
            
            # 出力列の指定
            st.subheader("出力列の指定")
            all_columns = df.columns.tolist()
            
            # 初回ロード時にはすべての列を選択
            if "selected_columns" not in st.session_state:
                st.session_state.selected_columns = all_columns.copy()
            
            # 選択されている列の更新
            selected_columns = st.multiselect(
                "出力する列を選択してください",
                all_columns,
                default=st.session_state.selected_columns
            )
            
            # 選択された列をセッション状態に保存
            st.session_state.selected_columns = selected_columns
            
            # 一括置換処理
            st.subheader("一括置換処理")
            
            # セッション状態の初期化
            if "replacements" not in st.session_state:
                st.session_state.replacements = []
            
            # 列追加ボタン
            if st.button("列の追加"):
                st.session_state.replacements.append({"column": "", "value": ""})
            
            # 置換設定を表示
            replace_columns = []
            replace_values = []
            
            for i, replacement in enumerate(st.session_state.replacements):
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    column = st.selectbox(
                        f"列 {i+1}",
                        selected_columns,
                        key=f"column_{i}"
                    )
                    replace_columns.append(column)
                
                with col2:
                    # content.idの場合はデフォルト値を「納品可」に
                    # content.statusの場合は選択リストを表示
                    if column == "content.status":
                        value = st.selectbox(
                            f"置換値 {i+1}",
                            options=["納品可", "チェック可"],
                            key=f"value_select_{i}"
                        )
                        replace_values.append(value)
                    else:
                        default_value = "納品可" if column == "content.id" else ""
                        value = st.text_input(
                            f"置換値 {i+1}",
                            value=default_value,
                            key=f"value_{i}"
                        )
                        replace_values.append(value)
                
                with col3:
                    if st.button("削除", key=f"delete_{i}"):
                        st.session_state.replacements.pop(i)
                        st.rerun()
            
            # 値変更ボタン
            if st.button("値を変更する") and selected_columns:
                # 選択された列だけを残す
                output_df = df[selected_columns].copy()
                
                # 置換処理
                for col, val in zip(replace_columns, replace_values):
                    if col and val:
                        output_df[col] = val
                
                # データ型の行を挿入（一括置換処理の後に実行）
                final_df = insert_data_types(output_df)
                
                st.session_state.output_df = final_df
                st.success("値の変更とデータ型の挿入が完了しました")
            
            # 処理結果の表示とダウンロード
            if "output_df" in st.session_state:
                st.subheader("処理結果")
                
                # データの行数を表示（データ型の行を除く）
                result_df = st.session_state.output_df
                actual_data_rows = len(result_df) - 1  # データ型の行を除く
                st.info(f"処理後のデータの行数: {actual_data_rows}行（データ型の行を除く）")
                
                st.dataframe(st.session_state.output_df)
                
                # ダウンロード設定
                st.subheader("ダウンロード設定")
                
                # エンコーディングの選択
                encoding = st.radio(
                    "エンコーディング",
                    options=["UTF-8", "Shift-JIS"],
                    index=1,  # インデックス1（Shift-JIS）をデフォルトに設定
                    horizontal=True
                )
                
                # エンコーディング設定を実際の値に変換
                encoding_value = 'utf-8' if encoding == "UTF-8" else 'shift_jis'
                
                # UTF-8が選択された場合のみBOMの選択肢を表示
                add_bom = False
                if encoding == "UTF-8":
                    add_bom = st.checkbox("BOMを付ける", value=True)
                
                # ダウンロードボタン
                csv_link = get_csv_download_link(
                    st.session_state.output_df, 
                    encoding=encoding_value, 
                    add_bom=add_bom
                )
                
                # 現在の日時を取得してフォーマット
                now = datetime.now()
                date_time_str = now.strftime("%Y%m%d_%H%M%S")
                
                # 元ファイル名を取得
                original_name = st.session_state.original_filename
                
                # ファイル名に冒頭に「インポート用」、元ファイル名、エンコード形式とBOMの情報、日時を含める
                # Shift-JISの場合はBOM情報を含めない
                if encoding == "UTF-8":
                    bom_info = "BOM付き" if add_bom else "BOMなし"
                    file_name = f"インポート用_{original_name}_{date_time_str}_{encoding}_{bom_info}.csv"
                else:
                    file_name = f"インポート用_{original_name}_{date_time_str}_{encoding}.csv"
                
                st.markdown(
                    f'<a href="{csv_link}" download="{file_name}" class="download-link">処理済みデータをダウンロード</a>',
                    unsafe_allow_html=True
                )
                
                # CSSスタイル
                st.markdown("""
                <style>
                .download-link {
                    background-color: #4CAF50;
                    color: white;
                    padding: 10px 20px;
                    text-align: center;
                    text-decoration: none;
                    display: inline-block;
                    font-size: 16px;
                    margin: 4px 2px;
                    cursor: pointer;
                    border-radius: 5px;
                }
                </style>
                """, unsafe_allow_html=True)
                
        except Exception as e:
            st.error(f"エラーが発生しました: {e}")

if __name__ == "__main__":
    main() 