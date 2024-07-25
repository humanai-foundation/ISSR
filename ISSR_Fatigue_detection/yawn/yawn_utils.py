import numpy as np
def yawn_aspect_ratio_SPIGA(landmarks_int):
    """
    AR Formula= AR=||P2-P6||+||P3-P5||/2*(||P2-P4||)
    """
    
    # compute the euclidean distances between the two sets of
    # vertical eye landmarks (x, y)-coordinates
    denominator_YAWN= np.linalg.norm(landmarks_int[91] - landmarks_int[88])  # Left Eye
    
    # ||P3-P5|| left
    yawn_89_95_dist=np.linalg.norm(landmarks_int[89] - landmarks_int[95])
   
    #||P2-P6|| left
    yawn_90_93_dist=np.linalg.norm(landmarks_int[90] - landmarks_int[93])
    
    yawn_AR=((yawn_89_95_dist+yawn_90_93_dist)/(2*denominator_YAWN))
    
    return yawn_AR