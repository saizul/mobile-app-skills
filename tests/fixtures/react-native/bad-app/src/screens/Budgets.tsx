import React from 'react';
import { ScrollView, Text, FlatList, Animated } from 'react-native';
import _ from 'lodash';
import AsyncStorage from '@react-native-community/async-storage';

export async function save(t: string) {
  await AsyncStorage.setItem('authToken', t);
  console.log('saved');
}

export function Budgets({ items }: { items: string[] }) {
  Animated.timing(new Animated.Value(0), { toValue: 1, useNativeDriver: false }).start();
  return (
    <ScrollView>
      {items.map(i => (
        <Text>{i}</Text>
      ))}
      <FlatList data={items} renderItem={({ item }) => <Text>{item}</Text>} />
    </ScrollView>
  );
}

const API = 'http://api.example.com';
