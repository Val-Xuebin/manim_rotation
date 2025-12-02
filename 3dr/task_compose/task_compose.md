batch_path = '/Users/valerio/Research/Manim/MRT-CubeStack/MRT/medias/batch_20251022_002829'

# multimodal part
'''easy compose
save all first and last
save s0_r0 videos

tasks
s0 r0 first as question
s0 r0 last as answer
s1 r0 last as mirror1
s2 r0 last as mirror2
s3 r0 last as modify

guidance videos
s0 r0 as guidance_easy
'''

'''hard compose
save all first and last: 
save s0_r0, s0_r1, s0_r2, s0_r3 videos

tasks
s0 r0 first as question
s0 r0 last as answer
s1 r1 last as mirror1
s2 r2 last as mirror2
s3 r3 last as modify

guidance videos
s0 r0 as guidance_answer
s0 r1 as guidance_mirror1
s0 r2 as guidance_mirror2
s0 r3 as guidance_modify (optional)
'''

# choice part
'''Randomly assign A/B/C/D to answer/mirror1/mirror2/modify for both easy and hard tasks
'''

# text part
f'''
Instruction: (system prompt)


Question:
According to the orginal <image1>,
which cubestack shown in the following images can be obtained through rotation.
A. <image2> B. <image3> C. <image4> D. <image5>

claim:
obstacles, blur, possible structure

Hard Answer:
<think>Let me focus on whether original cubestack can be rotated to the cubestack shown in the choices one by one. 
A. mirror1
For choice A, [it seems hard to tell if they are the same cubes. Let me visually imagine the original cubestack rotating to the supposed pose as the cubestack A. <imagine_video1>]
After visually rotating them, the cubestack in the choice A [is mirror-symmetric to the original and can not be obtained by rotating the original cube]
B. answer
choice B [is not obvious whether it's the same cube as the original. Let me visually imagine the original cubestack rotating to the supposed pose as the cubestack B. <imagine_video2>
After visually rotating the original cube, it matches the cubestack in the choice B. 
C. modify (miss)
[choice C misses one cube compared to the original cube, so it can not be obtained by rotating the original.]
[choice C is obtained by moving one cube's position]
D. mirror2
For choice A, [it seems hard to tell if they are the same cubes. Let me visually imagine the original cubestack rotating to the supposed pose as the cubestack A. <imagine_video3>]
After visually rotating them, the cubestack in the choice A [is mirror-symmetric to the original and can not be obtained by rotating the original cube]

</think><answer>B.</answer>

compile eg:
s1 r0 'mirror1'
sample: 
'C'-'<image4>'
<imagine>:'True/False' launch text: 'it seems hard to tell...'/'is not obvious'/''
''

'''

'''assign choice
"category": 'hard'
"id": 'mrt_h001'
"question": According to the orginal <image1>,which cubestack shown in the following images can be obtained through rotation.
A. <image2> B. <image3> C. <image4> D. <image5>. Answer with A./B./C./D.
"assign":{'A':'mirror1','B':'answer','C':'mirror2','D':'modify'}
"images":
    {
        'id_original.jpg',
        'id_mirror1.jpg',
        'id_answer.jpg',
        'id_mirror2.jpg',
        'id_remove/move.jpg'
    }
"guidance":
    {
        'id_guidance_mirror1.mp4',
        'id_guidance_answer.mp4',
        'id_guidance_mirror2.mp4',
        'id_guidance_remove/move.mp4'/'<no_guidance>'
    }
"answer": <answer>B.</answer>
"reasoning":<think>reserved text</think><answer>B.</answer>
'''

f'''assign choice
"category": 'easy'
"id": 'mrt_e001'
"question": According to the orginal <image1>,which cubestack shown in the following images can be obtained through rotation.
A. <image2> B. <image3> C. <image4> D. <image5>. Answer with A./B./C./D.
"assign":{'A':'answer','B':'mirror2','C':'modify','D':'mirror1'}
"images":
    {
        'id_original.jpg',
        'id_answer.jpg',
        'id_mirror2.jpg',
        'id_remove/move.jpg',
        'id_mirror1.jpg'
    }
"guidance":
    {
        'id_guidance_easy.mp4'
    }
"answer": <answer>A.</answer>
"reasoning":<think>reserved text</think><answer>A.</answer>
'''


'''Hard reasons:
    {
        'answer': 'is not obvious whether it's the same cube as the original. Let me visually imagine the original cubestack rotating to the supposed pose as the cubestack. <guidance_answer>
    After visually rotating the original cube, it matches the cubestack in the choice B. ',
        'mirror1': 'it seems hard to tell if they are the same cubes. Let me visually imagine the original cubestack rotating to the supposed pose.<guidance_mirror1>
    After visually rotating them, the cubestack is mirror-symmetric to the original and can not be obtained by rotating the original cube',
        'mirror2': 'is hard to tell if they are the same cubes. Let me visually imagine the original cubestack rotating to the supposed pose.<guidance_mirror2>
    After visually rotating them, the cubestack is mirror-symmetric to the original and can not be obtained by rotating the original cube'
        'move':
            {
                'under_guidance': 'Let me visually imagine the original cubestack rotating to the supposed pose.<guidance_move>, this cubestack is obtained by moving one cube's position',
                'no_guidance': 'is obtained by moving one cube's position'
            }
        'remove':
            {
                'under_guidance': 'Let me visually imagine the original cubestack rotating to the supposed pose.<guidance_move>, this cubestack is obtained by removing one cube's position',
                'no_guidance': 'misses one cube compared to the original cube, so it can not be obtained by rotating the original.'
            }
    }
'''

'''Easy reasons:
    {
        'answer': 'matches the rotated original cube in my imagination',
        'mirror1': ', based on the rotation imagination, the cubestack is mirror-symmetric to the original and can not be obtained by rotating the original cube',
        'mirror2': ', based on the rotation imagination, the cubestack is mirror-symmetric to the original and can not be obtained by rotating the original cube',
        'move': 'is obtained by moving one cube's position'
        'remove': 'misses one cube compared to the original cube, so it can not be obtained by rotating the original.'
    }
'''