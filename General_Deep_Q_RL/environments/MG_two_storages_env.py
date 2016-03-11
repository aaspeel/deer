"""
The environment simulates a microgrid consisting of short and long term storage. The agent can either choose to store in the long term storage or take energy out of it while the short term storage handle at best the lack or surplus of energy by discharging itself or charging itself respectively. Whenever the short term storage is empty and cannot handle the net demand a penalty (negative reward) is obtained equal to the value of loss load set to 2euro/kWh.
Two actions are possible for the agent:
- Action 0 corresponds to discharging the long-term storage
- Action 1 corresponds to charging the long-term storage
The state of the agent is made up of an history of two to four punctual observations:
- Charging state of the short term storage (0 is empty, 1 is full)
- Production and consumption (0 is no production or consumption, 1 is maximal production or consumption)
( - Distance to equinox )
( - Predictions of future production : average of the production for the next 24 hours and 48 hours )
More information can be found in the paper to be published :
Efficient decision making in stochastic micro-grids using deep reinforcement learning, Vincent Francois-Lavet, David Taralla, Raphael Fonteneau, Damien Ernst

Authors: Vincent Francois-Lavet, David Taralla
"""

import numpy as np
np.set_printoptions(threshold=np.nan)

from mpl_toolkits.axes_grid1 import host_subplot
import mpl_toolkits.axisartist as AA
import matplotlib.pyplot as plt
from base_classes import Environment
import copy

class MyEnv(Environment):
    def __init__(self, rng):
        """ Initialize environment

        Arguments:
            rng - the numpy random number generator
        """
        # Defining the type of environment
        self._dist_equinox=0
        self._pred=0
        
        inc_sizing=1.
        
        self._nActions = 3 

        if (self._dist_equinox==1 and self._pred==1):
            self._lastPonctualObservation = [0. ,[0.,0.],0., [0.,0.]]
            self._inputDimensions = [(1,), (12,2), (1,),(1,2)]
        elif (self._dist_equinox==1 and self._pred==0):
            self._lastPonctualObservation = [0. ,[0.,0.],0.]
            self._inputDimensions = [(1,), (12,2), (1,)]
        elif (self._dist_equinox==0 and self._pred==0):
            self._lastPonctualObservation = [0. ,[0.,0.]]
            self._inputDimensions = [(1,), (12,2)]

        self._rng = rng

        # Get consumption profile in [0,1]
        self.consumption_train_norm=np.load("data/example_nondeterminist_cons_train.npy")[0:1*365*24]
        self.consumption_valid_norm=np.load("data/example_nondeterminist_cons_train.npy")[365*24:2*365*24]
        self.consumption_test_norm=np.load("data/example_nondeterminist_cons_test.npy")[0:1*365*24]
        # Scale consumption profile in [0,2.1kW] --> average max per day = 1.7kW, average per day is 18.3kWh
        self.consumption_train=self.consumption_train_norm*2.1
        self.consumption_valid=self.consumption_valid_norm*2.1
        self.consumption_test=self.consumption_test_norm*2.1

        self.min_consumption=min(self.consumption_train)
        self.max_consumption=max(self.consumption_train)
        print("Sample of the consumption profile (kW): {}".format(self.consumption_train[0:24]))
        print("Min of the consumption profile (kW): {}".format(self.min_consumption))
        print("Max of the consumption profile (kW): {}".format(self.max_consumption))
        print("Average consumption per day train (kWh): {}".format(np.sum(self.consumption_train)/self.consumption_train.shape[0]*24))
        print("Average consumption per day valid (kWh): {}".format(np.sum(self.consumption_valid)/self.consumption_valid.shape[0]*24))
        print("Average consumption per day test (kWh): {}".format(np.sum(self.consumption_test)/self.consumption_test.shape[0]*24))

        # Get production profile in W/Wp in [0,1]
        self.production_train_norm=np.load("data/BelgiumPV_prod_train.npy")[0:1*365*24]
        self.production_valid_norm=np.load("data/BelgiumPV_prod_train.npy")[365*24:2*365*24] #determinist best is 110, "nondeterminist" is 124.9
        self.production_test_norm=np.load("data/BelgiumPV_prod_test.npy")[0:1*365*24] #determinist best is 76, "nondeterminist" is 75.2
        # Scale production profile : 12KWp (60m^2) et en kWh
        self.production_train=self.production_train_norm*12000./1000.*inc_sizing
        self.production_valid=self.production_valid_norm*12000./1000.*inc_sizing
        self.production_test=self.production_test_norm*12000/1000*inc_sizing

        self.min_production=min(self.production_train)
        self.max_production=max(self.production_train)
        print("Sample of the production profile (kW): {}".format(self.production_train[0:24]))
        print("Min of the production profile (kW): {}".format(self.min_production))
        print("Max of the production profile (kW): {}".format(self.max_production))
        print("Average production per day train (kWh): {}".format(np.sum(self.production_train)/self.production_train.shape[0]*24))
        print("Average production per day valid (kWh): {}".format(np.sum(self.production_valid)/self.production_valid.shape[0]*24))
        print("Average production per day test (kWh): {}".format(np.sum(self.production_test)/self.production_test.shape[0]*24))

        self.battery_size=15.*inc_sizing
        self.battery_eta=0.9
        
        self.hydrogen_max_power=1.1*inc_sizing
        self.hydrogen_eta=.65
        
    def reset(self, mode):
        """
        Returns:
           current observation (list of k elements)
        """
        ### Test 6
        if (self._dist_equinox==1 and self._pred==1):
            self._lastPonctualObservation = [1. ,[0.,0.],0., [0.,0.]]
        elif (self._dist_equinox==1 and self._pred==0):
            self._lastPonctualObservation = [1. ,[0.,0.],0.]
        elif (self._dist_equinox==0 and self._pred==0):
            self._lastPonctualObservation = [1. ,[0.,0.]]

        self.counter = 1        
        self.hydrogen_storage=0.
        
        if mode == -1:
            self.production_norm=self.production_train_norm
            self.production=self.production_train
            self.consumption_norm=self.consumption_train_norm
            self.consumption=self.consumption_train
        elif mode == 0:
            self.production_norm=self.production_valid_norm
            self.production=self.production_valid
            self.consumption_norm=self.consumption_valid_norm
            self.consumption=self.consumption_valid
        else:
            self.production_norm=self.production_test_norm
            self.production=self.production_test
            self.consumption_norm=self.consumption_test_norm
            self.consumption=self.consumption_test
            
        if (self._dist_equinox==1 and self._pred==1):
            return [
                        0., 
                        [[0. ,0.] for i in range(12)],
                        0.,
                        [0.,0.]
                    ]
        elif (self._dist_equinox==1 and self._pred==0):
            return [
                        0., 
                        [[0. ,0.] for i in range(12)],
                        0.
                    ]
        else: #elif (self._dist_equinox==0, self._pred==0):
            return [
                        0., 
                        [[0. ,0.] for i in range(12)],
                    ]
        
    def act(self, action):
        """
        Perform one time step on the environment
        """
        #print "NEW STEP"

        reward = 0#self.ale.act(action)  #FIXME
        terminal=0

        true_demand=self.consumption[self.counter-1]-self.production[self.counter-1]
        
        if (action==0):
            ## Energy is taken out of the hydrogen reserve
            true_energy_avail_from_hydrogen=-self.hydrogen_max_power*self.hydrogen_eta
            diff_hydrogen=-self.hydrogen_max_power
        if (action==1):
            ## No energy is taken out of/into the hydrogen reserve
            true_energy_avail_from_hydrogen=0
            diff_hydrogen=0
        if (action==2):
            ## Energy is taken into the hydrogen reserve
            true_energy_avail_from_hydrogen=self.hydrogen_max_power/self.hydrogen_eta
            diff_hydrogen=self.hydrogen_max_power
            
        reward=diff_hydrogen*0.1 # 0.1euro/kWh of hydrogen
        self.hydrogen_storage+=diff_hydrogen

        Energy_needed_from_battery=true_demand+true_energy_avail_from_hydrogen
        
        if (Energy_needed_from_battery>0):
        # Lack of energy
            if (self._lastPonctualObservation[0]*self.battery_size>Energy_needed_from_battery):
            # If enough energy in the battery, use it
                self._lastPonctualObservation[0]=self._lastPonctualObservation[0]-Energy_needed_from_battery/self.battery_size
            else:
            # Otherwise: use what is left and then penalty                
                reward-=(Energy_needed_from_battery-self._lastPonctualObservation[0]*self.battery_size)*2 #2euro/kWh
                self._lastPonctualObservation[0]=0
        elif (Energy_needed_from_battery<0):
        # Surplus of energy --> load the battery
            self._lastPonctualObservation[0]=min(1.,self._lastPonctualObservation[0]-Energy_needed_from_battery/self.battery_size*self.battery_eta)
                    
        #print "new self._lastPonctualObservation[0]"
        #print self._lastPonctualObservation[0]
        
        ### Test
        # self._lastPonctualObservation[0] : State of the battery (0=empty, 1=full)
        # self._lastPonctualObservation[1] : Normalized consumption at current time step (-> not available at decision time)
        # self._lastPonctualObservation[1][1] : Normalized production at current time step (-> not available at decision time)
        # self._lastPonctualObservation[2][0] : Prevision (accurate) for the current time step and the next 24hours
        # self._lastPonctualObservation[2][1] : Prevision (accurate) for the current time step and the next 48hours
        ###
        self._lastPonctualObservation[1][0]=self.consumption_norm[self.counter]
        self._lastPonctualObservation[1][1]=self.production_norm[self.counter]
        i=1
        if(self._dist_equinox==1):
            i=i+1
            self._lastPonctualObservation[i]=abs(self.counter/24-(365./2))/(365./2) #171 days between 1jan and 21 Jun
        if (self._pred==1):
            i=i+1
            self._lastPonctualObservation[i][0]=sum(self.production_norm[self.counter:self.counter+24])/24.#*self.rng.uniform(0.75,1.25)
            self._lastPonctualObservation[i][1]=sum(self.production_norm[self.counter:self.counter+48])/48.#*self.rng.uniform(0.75,1.25)
                                
        self.counter+=1
                
        return copy.copy(reward)

    def inputDimensions(self):
        return self._inputDimensions

    def nActions(self):
        return self._nActions

    def observe(self):
        return copy.deepcopy(self._lastPonctualObservation)     

    def summarizePerformance(self, test_data_set):
        print("summary perf")
        print("self.hydrogen_storage: {}".format(self.hydrogen_storage))
        i=0#180*24
        observations = test_data_set.observations()
        actions = test_data_set.actions()
        print("observations, actions")
        print(observations[0+i:100+i], actions[0+i:100+i])

        battery_level=observations[0][0+i:100+i]
        consumption=observations[1][:,0][0+i:100+i]
        production=observations[1][:,1][0+i:100+i]
        actions=actions[0+i:100+i]
        
        battery_level=np.array(battery_level)*self.battery_size
        consumption=np.array(consumption)*(self.max_consumption-self.min_consumption)+self.min_consumption
        production=np.array(production)*(self.max_production-self.min_production)+self.min_production

        steps=np.arange(100)
        print(steps)
        print("battery_level")
        print(battery_level[0+i:100+i])
        print(consumption[0+i:100+i])
        print(production[0+i:100+i])
        
        steps_long=np.arange(1000)/10.
        
        
        host = host_subplot(111, axes_class=AA.Axes)
        plt.subplots_adjust(left=0.2, right=0.8)
        
        par1 = host.twinx()
        par2 = host.twinx()
        par3 = host.twinx()
        
        offset = 60
        new_fixed_axis = par2.get_grid_helper().new_fixed_axis
        par2.axis["right"] = new_fixed_axis(loc="right",
                                            axes=par2,
                                            offset=(offset, 0))    
        par2.axis["right"].toggle(all=True)
        
        offset = -60
        new_fixed_axis = par3.get_grid_helper().new_fixed_axis
        par3.axis["right"] = new_fixed_axis(loc="left",
                                            axes=par3,
                                            offset=(offset, 0))    
        par3.axis["right"].toggle(all=True)
        
        
        host.set_xlim(-0.9, 99)
        host.set_ylim(0, 15.9)
        
        host.set_xlabel("Time")
        host.set_ylabel("Battery level")
        par1.set_ylabel("Consumption")
        par2.set_ylabel("Production")
        par3.set_ylabel("H Actions")
        
        p1, = host.plot(steps, battery_level, marker='o', lw=1, c = 'b', alpha=0.8, ls='-', label = 'Battery level')
        print(steps_long.shape)
        print(np.repeat(consumption,10).shape)
        p2, = par1.plot(steps_long-0.9, np.repeat(consumption,10), lw=3, c = 'r', alpha=0.5, ls='-', label = 'Consumption')
        p3, = par2.plot(steps_long-0.9, np.repeat(production,10), lw=3, c = 'g', alpha=0.5, ls='-', label = 'Production')
        p4, = par3.plot(steps_long, np.repeat(actions,10), lw=3, c = 'c', alpha=0.5, ls='-', label = 'H Actions')
        
        par1.set_ylim(0, 10.09)
        par2.set_ylim(0, 10.09)
        par3.set_ylim(-0.09, 2.09)
        
        host.legend(loc=1)#loc=9)
        
        host.axis["left"].label.set_color(p1.get_color())
        par1.axis["right"].label.set_color(p2.get_color())
        par2.axis["right"].label.set_color(p3.get_color())
        par3.axis["right"].label.set_color(p4.get_color())
        
        plt.savefig("plot.png")
        
        plt.draw()
        plt.show()
        plt.close('all')
        
def main():
    rng = np.random.RandomState(123456)
    myenv=MyEnv(rng)

    myenv.reset(False)
    
    
    print(myenv.observe())
    print(myenv.act(2, False))
    print(myenv.observe())
    print(myenv.act(2, False))
    print(myenv.observe())
    print(myenv.act(0, False))
    print(myenv.observe())
    print(myenv.act(1, False))
    print(myenv.observe())
    print(myenv.act(1, False))
    print(myenv.observe())
    print(myenv.act(2, False))
    print(myenv.observe())
    print(myenv.act(2, False))
    print(myenv.observe())
    print(myenv.act(2, False))
    print(myenv.observe())
    print(myenv.act(2, False))
    print(myenv.observe())
    print(myenv.act(2, False))
    print(myenv.observe())
    print(myenv.act(1, False))
    print(myenv.observe())
    print(myenv.act(1, False))
    print(myenv.observe())
    
    
if __name__ == "__main__":
    main()
