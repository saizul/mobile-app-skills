import { FlatList, Text } from 'react-native';
import debounce from 'lodash/debounce';
export const Budgets = ({ items }: { items: { id: string; name: string }[] }) => (
  <FlatList data={items} keyExtractor={item => item.id} renderItem={({ item }) => <Text>{item.name}</Text>} />
);
console.log('dev only');
export const search = debounce(() => {}, 300);
