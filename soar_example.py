'''
Created on Oct 7, 2016

@author: smohan
'''

from os import environ as env
import sys, getopt
import os
import re
import time
from threading import Thread
from collections import defaultdict


### point the platform-relevant path variable to SoarSuite/bin
if "DYLD_LIBRARY_PATH" in env:
    LIB_PATH = env["DYLD_LIBRARY_PATH"]
elif "LD_LIBRARY_PATH" in env:
    LIB_PATH = env["LD_LIBRARY_PATH"]
else:
    print("Soar LIBRARY_PATH environment variable not set; quitting")
    exit(1)
sys.path.append(LIB_PATH)
import Python_sml_ClientInterface as sml

global agents
agents = {}
    
global kernels
kernels = {}
    
global threads 
threads = []

global kernel_agents
kernel_agents = defaultdict(list)


def create_kernel(kernel_counter):
    kernel = sml.Kernel.CreateKernelInNewThread()
    if not kernel or kernel.HadError():
        print("Error creating kernel: " + kernel.GetLastErrorDescription())
        exit(1)
    print("Created Soar kernel.")
    kernels[kernel] = 'kernel-%d'%kernel_counter
    return kernel

def create_agent(kernel, name):
    agent = kernel.CreateAgent(name)
    if not agent:
        print("Error creating agent: " + kernel.GetLastErrorDescription())
        exit(1)
    print("Created agent: %s" % name)
    return agent

def load_agent_rules(agent, agentFile):
    agent.LoadProductions(os.path.realpath(agentFile));
    print("Loaded rules in %s" % agents.get(agent))

# callback registry
def register_print_callback(kernel, agent, function, user_data=None):
    agent.RegisterForPrintEvent(sml.smlEVENT_PRINT, function, agent)
    print("%s registered for print callbacks" % agents.get(agent))
    
def callback_print_message(mid, user_data, agent, message):
    message = message.strip()
    if (not message.startswith(" Soar 9.5.0")):
        print ("[%s] :: %s" % (agents.get(user_data), message))
        pass
    
def run_all_agents(kernel):
    print("Running all agents")
    t = Thread(target=run_everyone_forever, args=(kernel,))
    t.start()
    threads.append(t)
    
def run_everyone_forever(kernel):
    kernel.RunAllAgentsForever()
    
def run_multiple_agents_in_single_kernel(kernel_counter, num_agents):
    ### running multiple agents in a single kernel
    kernel = create_kernel(kernel_counter)
    for a in range(0, num_agents):
        agent_name = 'agent-%d' % a
        agent = create_agent(kernel, agent_name)
        agents[agent] = agent_name
        register_print_callback(kernel, agent, callback_print_message)
        load_agent_rules(agent, "./Water_Jug_Tie_Agent/water-jug-tie.soar")
        kernel_agents[kernel].append(agent)
    run_all_agents(kernel)
    return kernel_counter
    
def run_multiple_agents_one_agent_per_kernel(kernel_counter, num_agents):
    ### 1 agent/kernel; 50 kernels in threads
    for a in range(0, num_agents):
        agent_name = 'agent-%d' % a
        kernel = create_kernel(kernel_counter)
        agent = create_agent(kernel, agent_name)
        agents[agent] = agent_name
        register_print_callback(kernel, agent, callback_print_message)
        load_agent_rules(agent, "./Water_Jug_Tie_Agent/water-jug-tie.soar")
        kernel_agents[kernel].append(agent)
        run_all_agents(kernel)
        kernel_counter = kernel_counter + 1
    return kernel_counter

def get_agent_stats():
    
    sum_agents_average_decision_time = 0
    sum_agents_max_decision_time = 0
    
    agent_counter = 0
    
    for agent in agents:
        stats = agent.ExecuteCommandLine("stats")
        maxstats = agent.ExecuteCommandLine("stats -M")
        avg_decision_time = re.sub(".*\((.*) msec/decision.*", r"\1", stats, flags=re.DOTALL)
        max_decision_time = re.sub(".*  Time \(sec\) *([0-9.]*).*", r"\1", maxstats, flags=re.DOTALL)
        print("[%s] ::" % agents[agent]),
        print("average decision time: %s msec/decision" % avg_decision_time)
        print("             maximum decision time: %f msec/decision" % (float(max_decision_time) * 1000))
        sum_agents_average_decision_time = sum_agents_average_decision_time + float(avg_decision_time)
        sum_agents_max_decision_time = sum_agents_max_decision_time + float(max_decision_time) * 1000
        agent_counter = agent_counter + 1
        
    avg_agents_average_decision_time = sum_agents_average_decision_time / agent_counter
    avg_agents_max_decision_time = sum_agents_max_decision_time / agent_counter
    
    return avg_agents_average_decision_time, avg_agents_max_decision_time
        
                        

if __name__ == '__main__':

    kernel_counter = 1
    mode = ''
    # parse command line input
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hn:m:", ["num-agents=", "mode="])
    except getopt.GetoptError as err:
        print str(err)
        print 'usage: python multi_agent_example -n <number of agents> -m <single/multi>'
        sys.exit(2)
        
    for opt,arg in opts:
        if opt == '-h':
            print "usage: python multi_agent_example -n <number of agents> -m <single/multi>"
            sys.exit(2)
        elif opt in ("-n", "--num-agents"):
            num_agents = int(float(arg))
        elif opt in("-m", "--mode"):
            mode = arg
    

    if (mode == "single"):
        kernel_counter = run_multiple_agents_in_single_kernel(kernel_counter, num_agents)
    if (mode == "multi"):
        kernel_counter = run_multiple_agents_one_agent_per_kernel(kernel_counter, num_agents)
    
    for thread in threads:
        thread.join()
        pass
    
    avg_avg_decision, avg_max_decision = get_agent_stats()
    
    for kernel in kernels:
        for agent in kernel_agents[kernel]:
            print("Destroying agent:%s in kernel:%s." % (agents[agent], kernels[kernel]))
            kernel.DestroyAgent(agent)
        print("Shutting down kernel: %s" % kernels[kernel])
        kernel.Shutdown()
        
        
    print ("------------------------------- Time Report --------------------------------------")
    print ("Average time taken by %d agents to run a typical decision cycle: %f msecs" % (num_agents, avg_avg_decision))
    print ("Average time taken by %d agents to run the costliest decision cycle: %f msecs" % (num_agents, avg_max_decision))
    print ("----------------------------------------------------------------------------------")
    