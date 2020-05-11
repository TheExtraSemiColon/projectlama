import pickle
from collections import defaultdict

arr = pickle.load(open("sample.pkl", "rb"))
(max, min, tot, num) = (0 , 0, 0.0 , 0)
(max_index, min_index) = (0, 0)

for Q in arr:
	tot = tot + arr[Q]
	num+=1
	if arr[Q]> max:
		max = arr[Q]
		max_index = Q
	if arr[Q] < min:
		min = arr[Q]
		min_index = Q


avg = tot/num

print(f"MAX Q_VALUE INDEX: {max_index}, and Q_VALUE: {max}")
print(f"MIN Q_VALUE INDEX: {min_index}, and Q_VALUE: {min}")
print(f"AVERAGE: {avg}")
