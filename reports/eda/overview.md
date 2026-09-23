# Dataset overview

- Data directory: `/home/jovyan/scratch/home-migrate/bachdx2/VinRepo/LongitudinalResearch/physionet.org/files/chest-imagenome/1.0.0`
- Files: 71
- CSV tables: 16

| CSV | Rows | Columns | Column names |
|---|---:|---:|---|
| `analysis/affirmed_attributes_eval4paper.csv` | 70 | 8 | attribute, freq, TP, FN, FP, precision, recall, f1-score |
| `analysis/affirmed_bboxes_across_attributes_report_level.csv` | 38 | 8 | bbox_name, freq, TP, FN, FP, precision, recall, f1-score |
| `analysis/object_to_attribute_relation_stats.csv` | 683 | 4 | bbox, attribute, freq_nlp, freq_has_bbox |
| `analysis/object_to_object_comparison_relation_stats.csv` | 2681 | 5 | bbox, comparison, attribute, freq_nlp, freq_have_bboxes |
| `gold_dataset/bbox_coordinate_annotations_1_C.csv` | 16996 | 15 | image_id, x1, y1, x2, y2, width, height, bbox_name, annot_id, original_x1, original_x2, original_y1, original_y2, original_width, original_height |
| `gold_dataset/bbox_coordinate_annotations_1_W.csv` | 16995 | 15 | image_id, x1, y1, x2, y2, width, height, bbox_name, annot_id, original_x1, original_x2, original_y1, original_y2, original_width, original_height |
| `gold_dataset/bbox_coordinate_annotations_2_J.csv` | 16934 | 15 | image_id, x1, y1, x2, y2, width, height, bbox_name, annot_id, original_x1, original_x2, original_y1, original_y2, original_width, original_height |
| `gold_dataset/bbox_coordinate_annotations_2_S.csv` | 16998 | 15 | image_id, x1, y1, x2, y2, width, height, bbox_name, annot_id, original_x1, original_x2, original_y1, original_y2, original_width, original_height |
| `gold_dataset/gold_bbox_coordinate_annotations_1000images.csv` | 25989 | 18 | image_id, x1, y1, x2, y2, width, height, bbox_name, annot_id, original_x1, original_x2, original_y1, original_y2, original_width, original_height, annotator, coord224, coord_original |
| `gold_dataset/gold_bbox_scaling_factors_original_to_224x224.csv` | 1000 | 6 | image_id, top, bottom, left, right, ratio |
| `silver_dataset/splits/images_to_avoid.csv` | 3821 | 5 | subject_id, study_id, dicom_id, path, ViewPosition |
| `silver_dataset/splits/test.csv` | 47393 | 6 | , subject_id, study_id, dicom_id, path, ViewPosition |
| `silver_dataset/splits/train.csv` | 166521 | 6 | , subject_id, study_id, dicom_id, path, ViewPosition |
| `silver_dataset/splits/valid.csv` | 23953 | 6 | , subject_id, study_id, dicom_id, path, ViewPosition |
| `utils/cxr-record-list_view.csv` | 377110 | 5 | subject_id, study_id, dicom_id, path, ViewPosition |
| `utils/cxr-study-list_v2.csv` | 227835 | 5 | subject_id, study_id, path, gender, age_decile |

See `file_inventory.csv` for file sizes and formats.
