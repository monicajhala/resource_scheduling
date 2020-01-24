# resource_scheduling
The INPUTS for the model are:
•	Employee ID
•	Start Date 
•	End Date 
•	Project
•	Shift 
1.	Morning
2.	Evening
3.	Night
Constraints 
•	Not more than 40 hours worked per day.
•	If worker work that morning, cannot work that day.
•	If worker working that evening, until next evening.
•	If worker working in night, until next night.

Objective Function 
•	To pass the list of workers for the optimal solution.
•	To build a week table for the workers.
•	Swapping the shifts; the morning shift to night, evening to morning & night to evening.
Results 
The mixed integer programming is chosen for the scheduling the resources(workers) 
because the MIP gives the integer values in return at the optimal solution.
In our case, the objective function is defining such that the number of workers required
for a particular shift should not work in a consecutive shift and every worker work should be allocated.
MIP is the best method to solve this problem and it is practice everywhere for solving resource scheduling problems.  

